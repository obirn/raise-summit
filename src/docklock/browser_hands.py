from __future__ import annotations

import asyncio
import base64
from typing import Any
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, Page, Playwright, Route, async_playwright

from .schemas import ActionCommand, DomTarget


class NavigationBlockedError(RuntimeError):
    pass


class BrowserHands:
    """Playwright execution layer with coordinate scaling and network allowlisting."""

    def __init__(
        self,
        *,
        start_url: str = "http://localhost:3000",
        allowed_origins: tuple[str, ...] = ("http://localhost:3000",),
        viewport_width: int = 1440,
        viewport_height: int = 900,
        headless: bool = False,
    ) -> None:
        self.start_url = start_url
        self.allowed_origins = set(allowed_origins)
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.headless = headless
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self.page: Page | None = None

    async def __aenter__(self) -> "BrowserHands":
        await self.start()
        return self

    async def __aexit__(self, exc_type: object, exc: BaseException | None, tb: object) -> None:
        await self.close()

    @property
    def url(self) -> str:
        return self._page.url

    @property
    def _page(self) -> Page:
        if self.page is None:
            raise RuntimeError("BrowserHands has not been started")
        return self.page

    async def start(self) -> None:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        self._context = await self._browser.new_context(
            viewport={"width": self.viewport_width, "height": self.viewport_height},
            accept_downloads=False,
        )
        await self._context.route("**/*", self._route_request)
        self.page = await self._context.new_page()
        await self.safe_goto(self.start_url)

    async def close(self) -> None:
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def _route_request(self, route: Route) -> None:
        url = route.request.url
        if self.is_allowed_url(url):
            await route.continue_()
        else:
            print(f"[hands] blocked external request: {url}")
            await route.abort()

    def is_allowed_url(self, url: str) -> bool:
        parsed = urlparse(url)
        if parsed.scheme in {"about", "data", "blob"}:
            return True
        origin = f"{parsed.scheme}://{parsed.netloc}"
        return origin in self.allowed_origins

    async def safe_goto(self, url: str) -> None:
        if not self.is_allowed_url(url):
            raise NavigationBlockedError(f"Navigation outside allowlist blocked: {url}")
        await self._page.goto(url, wait_until="domcontentloaded")

    async def viewport_size(self) -> tuple[int, int]:
        viewport = self._page.viewport_size
        if viewport:
            return int(viewport["width"]), int(viewport["height"])
        size = await self._page.evaluate("[window.innerWidth, window.innerHeight]")
        return int(size[0]), int(size[1])

    async def scale_coordinates(self, x: int, y: int) -> tuple[int, int]:
        width, height = await self.viewport_size()
        return int(x / 1000 * width), int(y / 1000 * height)

    async def resolve_dom_at_normalized(self, x: int, y: int) -> DomTarget | None:
        real_x, real_y = await self.scale_coordinates(x, y)
        snapshot = await self._page.evaluate(
            """
            ([x, y]) => {
              const direct = document.elementFromPoint(x, y);
              if (!direct) return null;
              const actionable = direct.closest(
                'button,a,input,textarea,select,label,[role="button"],[data-action]'
              ) || direct;

              const attrs = {};
              for (const name of [
                'id', 'class', 'name', 'type', 'role', 'aria-label',
                'value', 'href', 'placeholder', 'data-action', 'data-testid',
                'data-field', 'data-portal'
              ]) {
                const value = actionable.getAttribute(name);
                if (value) attrs[name] = value;
              }
              if (actionable.id) attrs.id = actionable.id;
              if (actionable.className && typeof actionable.className === 'string') {
                attrs.class = actionable.className;
              }

              const rawText = actionable.innerText ||
                actionable.textContent ||
                actionable.value ||
                actionable.getAttribute('aria-label') ||
                '';

              return {
                tag: actionable.tagName.toLowerCase(),
                text: String(rawText).replace(/\\s+/g, ' ').trim().slice(0, 500),
                attributes: attrs,
                x,
                y
              };
            }
            """,
            [real_x, real_y],
        )
        if not snapshot:
            return None
        return DomTarget(
            tag=str(snapshot["tag"]),
            text=str(snapshot["text"]),
            attributes={str(k): str(v) for k, v in snapshot.get("attributes", {}).items()},
            x=int(snapshot["x"]),
            y=int(snapshot["y"]),
        )

    async def execute(self, command: ActionCommand) -> dict[str, Any]:
        name = command.name
        args = command.arguments
        print(f"[hands] executing {name} intent={args.get('intent', 'n/a')!r}")

        if name in {"click", "click_at"}:
            x, y = await self.scale_coordinates(int(args["x"]), int(args["y"]))
            await self._page.mouse.click(x, y)
            return {"clicked": {"x": x, "y": y}}

        if name == "double_click":
            x, y = await self.scale_coordinates(int(args["x"]), int(args["y"]))
            await self._page.mouse.dblclick(x, y)
            return {"double_clicked": {"x": x, "y": y}}

        if name in {"middle_click", "right_click"}:
            x, y = await self.scale_coordinates(int(args["x"]), int(args["y"]))
            button = "middle" if name == "middle_click" else "right"
            await self._page.mouse.click(x, y, button=button)
            return {"clicked": {"x": x, "y": y, "button": button}}

        if name == "move":
            x, y = await self.scale_coordinates(int(args["x"]), int(args["y"]))
            await self._page.mouse.move(x, y)
            return {"moved": {"x": x, "y": y}}

        if name in {"type", "type_text_at"}:
            if "x" in args and "y" in args:
                x, y = await self.scale_coordinates(int(args["x"]), int(args["y"]))
                await self._page.mouse.click(x, y)
            if args.get("clear_before_typing", True):
                await self._page.keyboard.press("Meta+A")
                await self._page.keyboard.press("Backspace")
            await self._page.keyboard.type(str(args["text"]))
            if args.get("press_enter", False):
                await self._page.keyboard.press("Enter")
            return {"typed": str(args["text"])}

        if name == "press_key":
            await self._page.keyboard.press(str(args["key"]))
            return {"pressed_key": str(args["key"])}

        if name in {"hotkey", "key_combination"}:
            keys = args.get("keys")
            chord = "+".join(keys) if isinstance(keys, list) else str(keys)
            await self._page.keyboard.press(chord)
            return {"hotkey": chord}

        if name == "scroll":
            x, y = await self.scale_coordinates(int(args.get("x", 500)), int(args.get("y", 500)))
            await self._page.mouse.move(x, y)
            magnitude = int(args.get("magnitude_in_pixels", 300))
            direction = str(args.get("direction", "down")).lower()
            dx, dy = 0, 0
            if direction == "down":
                dy = magnitude
            elif direction == "up":
                dy = -magnitude
            elif direction == "right":
                dx = magnitude
            elif direction == "left":
                dx = -magnitude
            await self._page.mouse.wheel(dx, dy)
            return {"scrolled": {"direction": direction, "magnitude": magnitude}}

        if name == "navigate":
            await self.safe_goto(str(args["url"]))
            return {"navigated": self.url}

        if name == "go_back":
            await self._page.go_back(wait_until="domcontentloaded")
            return {"url": self.url}

        if name == "go_forward":
            await self._page.go_forward(wait_until="domcontentloaded")
            return {"url": self.url}

        if name == "wait":
            seconds = float(args.get("seconds", 1))
            await asyncio.sleep(seconds)
            return {"waited_seconds": seconds}

        if name == "take_screenshot":
            return {"screenshot": await self.screenshot_base64()}

        raise NotImplementedError(f"Unsupported action: {name}")

    async def screenshot_base64(self) -> str:
        image = await self._page.screenshot(type="png")
        return base64.b64encode(image).decode("utf-8")

    async def visible_text(self) -> str:
        return await self._page.evaluate("document.body ? document.body.innerText : ''")

    async def extract_invoice_line_items(self) -> list[dict[str, Any]]:
        """Extract visible invoice-like line items with dollar amounts from the current page."""

        return await self._page.evaluate(
            """
            () => {
              const moneyPattern = /\\$\\s*\\d{1,3}(?:,\\d{3})*(?:\\.\\d{2})?/g;
              const candidates = [
                ...document.querySelectorAll(
                  'tr, li, [data-invoice-line], [data-line-item], .invoice-line, .line-item'
                )
              ];

              const rows = candidates.length ? candidates : [document.body];
              const items = [];
              for (const row of rows) {
                const text = (row.innerText || row.textContent || '').replace(/\\s+/g, ' ').trim();
                if (!text) continue;

                const amounts = text.match(moneyPattern) || [];
                for (const amountText of amounts) {
                  const amount = Number(amountText.replace(/[$,\\s]/g, ''));
                  const label = text.replace(amountText, '').replace(/[:|\\-]+$/g, '').trim();
                  items.push({label, amount, amount_text: amountText});
                }
              }

              const deduped = [];
              const seen = new Set();
              for (const item of items) {
                const key = `${item.label}|${item.amount}`;
                if (seen.has(key)) continue;
                seen.add(key);
                deduped.push(item);
              }
              return deduped;
            }
            """
        )

    async def inspect_errors(self) -> str | None:
        errors = await self._page.evaluate(
            """
            () => {
              const selectors = [
                '.error-message',
                '.alert-error',
                '.toast-error',
                '[role="alert"]',
                '[data-status="rejected"]'
              ];
              const chunks = [];
              for (const selector of selectors) {
                for (const node of document.querySelectorAll(selector)) {
                  const text = (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim();
                  if (text) chunks.push(text);
                }
              }
              const body = document.body ? document.body.innerText : '';
              for (const pattern of ['DECLARATION: REJECTED', '[ DECLARATION: REJECTED ]']) {
                if (body.includes(pattern)) chunks.push(pattern);
              }
              return [...new Set(chunks)].join(' | ') || null;
            }
            """
        )
        return str(errors) if errors else None
