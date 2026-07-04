"""Artifact writer — screenshots for the audit trail (invariant 5).

Every read/act persists a screenshot here; the coordinator UI renders these as
demurrage-dispute evidence. Real Computer Use passes PNG bytes from Playwright;
the M1 stub writes a labelled placeholder so audit paths exist end-to-end.
"""

from __future__ import annotations

import os
import struct
import time
import zlib

ARTIFACTS_DIR = os.environ.get("ARTIFACTS_DIR", "artifacts")


def _placeholder_png() -> bytes:
    """A minimal valid 1x1 PNG (so the file is a real image, not empty)."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\xcc\xcc\xcc"  # one grey pixel
    idat = zlib.compress(raw)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def save_bytes(prefix: str, data: bytes) -> str:
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    path = os.path.join(ARTIFACTS_DIR, f"{prefix}_{int(time.time() * 1000)}.png")
    with open(path, "wb") as f:
        f.write(data)
    return path


def save_screenshot(prefix: str) -> str:
    """DEMO-ONLY placeholder. Real CU calls save_bytes(prefix, png_from_playwright)."""
    return save_bytes(prefix, _placeholder_png())
