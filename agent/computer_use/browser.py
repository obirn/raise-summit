"""Playwright browser driver for Computer Use (headful).

Low-level primitives implementing the Gemini 2.5 Computer Use *legacy* action
vocabulary against a single persistent, headful Chromium context. State (the
portals' localStorage) lives in the browser profile — reachable ONLY through
this rendered UI, never a backend (invariant 1). Coordinates arrive already
denormalized to pixels (the worker scales the model's 0–1000 space).

Sync Playwright objects are thread-bound: construct and use this on ONE thread
(the CU worker thread owns it).
"""

from __future__ import annotations

import os
import time

from playwright.sync_api import sync_playwright

CU_PROFILE_DIR = os.environ.get("CU_PROFILE_DIR", ".cu_profile")
VIEWPORT_W = int(os.environ.get("CU_VIEWPORT_W", "1440"))
VIEWPORT_H = int(os.environ.get("CU_VIEWPORT_H", "900"))
CU_HEADLESS = os.environ.get("CU_HEADLESS", "0") == "1"


class BrowserComputer:
    def __init__(self) -> None:
        self._pw = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            user_data_dir=CU_PROFILE_DIR,
            headless=CU_HEADLESS,
            viewport={"width": VIEWPORT_W, "height": VIEWPORT_H},
            args=["--disable-blink-features=AutomationControlled"],
        )
        self.page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()

    # ---- observation -------------------------------------------------------
    def screenshot(self) -> bytes:
        return self.page.screenshot(type="png")

    def screen_size(self) -> tuple[int, int]:
        return (VIEWPORT_W, VIEWPORT_H)

    def is_alive(self) -> bool:
        """False if the page/context/browser was closed (window shut, crash…)."""
        try:
            return self.page is not None and not self.page.is_closed()
        except Exception:  # noqa: BLE001
            return False

    def current_url(self) -> str:
        return self.page.url

    def collect_data_fields(self) -> list[dict]:
        """Every [data-field] element with its text + data-* attributes. This is
        how the worker extracts structured Observation.fields deterministically —
        it reads what is rendered on screen, nothing hidden."""
        return self.page.eval_on_selector_all(
            "[data-field]",
            """els => els.map(el => ({
                field: el.getAttribute('data-field'),
                text: (el.innerText || '').trim().slice(0, 200),
                dataset: Object.assign({}, el.dataset),
            }))""",
        )

    # ---- actions (legacy vocabulary; coords in pixels) ---------------------
    def navigate(self, url: str) -> None:
        self.page.goto(url, wait_until="domcontentloaded")

    def click_at(self, x: int, y: int) -> None:
        self.page.mouse.click(x, y)

    def hover_at(self, x: int, y: int) -> None:
        self.page.mouse.move(x, y)

    def type_text_at(self, x: int, y: int, text: str, press_enter: bool = False,
                     clear_before_typing: bool = True) -> None:
        self.page.mouse.click(x, y)
        if clear_before_typing:
            self.page.keyboard.press("Control+A")
            self.page.keyboard.press("Delete")
        self.page.keyboard.type(text)
        if press_enter:
            self.page.keyboard.press("Enter")

    def scroll_document(self, direction: str) -> None:
        dy = {"up": -800, "down": 800}.get(direction, 0)
        dx = {"left": -800, "right": 800}.get(direction, 0)
        self.page.mouse.wheel(dx, dy)

    def scroll_at(self, x: int, y: int, direction: str, magnitude: int = 800) -> None:
        self.page.mouse.move(x, y)
        dy = {"up": -magnitude, "down": magnitude}.get(direction, 0)
        dx = {"left": -magnitude, "right": magnitude}.get(direction, 0)
        self.page.mouse.wheel(dx, dy)

    def key_combination(self, keys: str) -> None:
        combo = "+".join(part.capitalize() if len(part) == 1 else part
                         for part in keys.split("+"))
        self.page.keyboard.press(combo)

    def drag_and_drop(self, x: int, y: int, destination_x: int, destination_y: int) -> None:
        self.page.mouse.move(x, y)
        self.page.mouse.down()
        self.page.mouse.move(destination_x, destination_y)
        self.page.mouse.up()

    def go_back(self) -> None:
        self.page.go_back()

    def go_forward(self) -> None:
        self.page.go_forward()

    def wait_5_seconds(self) -> None:
        time.sleep(5)

    def open_web_browser(self) -> None:
        pass  # already open

    def close(self) -> None:
        try:
            self._ctx.close()
        finally:
            self._pw.stop()
