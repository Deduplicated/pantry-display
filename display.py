"""
display.py — Renders the produce expiry list as an 800x480 monochrome image
and pushes it to the Waveshare 7.5" e-paper display.

DEV MODE
--------
Set the environment variable DEV_MODE=1 (or run on a machine without the
Waveshare library installed) to skip all hardware calls.  The rendered image
is saved as preview.png in the project directory instead.

HARDWARE NOTES
--------------
The Waveshare 7.5" v2 HAT uses the epd7in5_V2 driver.  If you have a
different version (v1, v3, etc.) change the import on the line marked
"# WAVESHARE DRIVER IMPORT" below to the correct module name.
Driver modules live in the waveshare_epd package installed from:
  https://github.com/waveshare/e-Paper/tree/master/RaspberryPi_JetsonNano/python
"""

import os
import sys
from datetime import date, datetime

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PREVIEW_PATH = os.path.join(BASE_DIR, "preview.png")

# ---------------------------------------------------------------------------
# Display dimensions (Waveshare 7.5" v2)
# ---------------------------------------------------------------------------
WIDTH = 800
HEIGHT = 480

# ---------------------------------------------------------------------------
# Dev-mode detection
# ---------------------------------------------------------------------------
# We are in dev mode if:
#   1. The DEV_MODE env var is set to a truthy value, OR
#   2. The waveshare_epd package cannot be imported (not running on Pi)
DEV_MODE = os.environ.get("DEV_MODE", "0").strip() not in ("0", "false", "False", "")

if not DEV_MODE:
    try:
        # WAVESHARE DRIVER IMPORT — change epd7in5_V2 if you have a different version
        from waveshare_epd import epd7in5_V2 as epd_driver
    except ImportError:
        print("[display] waveshare_epd not found — falling back to dev mode.")
        DEV_MODE = True

# ---------------------------------------------------------------------------
# Font helpers
# ---------------------------------------------------------------------------
# We try system fonts that are typically present on Raspberry Pi OS and macOS.
# Pillow's ImageFont.truetype raises OSError if the file is not found.

def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",  # macOS fallback
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    # Last resort: Pillow's built-in bitmap font (no size control)
    return ImageFont.load_default()


# Pre-load fonts at module level so they are reused across renders
FONT_TITLE   = _load_font(36, bold=True)
FONT_SECTION = _load_font(22, bold=True)
FONT_ITEM    = _load_font(22, bold=False)
FONT_SMALL   = _load_font(18, bold=False)

# ---------------------------------------------------------------------------
# Grouping logic
# ---------------------------------------------------------------------------

def _days_remaining(expiry_date_str: str) -> int:
    """Return signed integer days until expiry (negative = already expired)."""
    expiry = date.fromisoformat(expiry_date_str)
    return (expiry - date.today()).days


def _group_items(items: list[dict]) -> dict[str, list[tuple[str, int]]]:
    """
    Sort items into display groups.
    Returns an ordered dict:
      { "EXPIRED": [...], "USE FIRST": [...], "THIS WEEK": [...], "FRESH": [...] }
    Each list contains (name, days_remaining) tuples, sorted by days ascending.
    """
    groups: dict[str, list[tuple[str, int]]] = {
        "EXPIRED":   [],
        "USE FIRST": [],
        "THIS WEEK": [],
        "FRESH":     [],
    }
    for item in items:
        days = _days_remaining(item["expiry_date"])
        entry = (item["name"], days)
        if days < 0:
            groups["EXPIRED"].append(entry)
        elif days <= 2:
            groups["USE FIRST"].append(entry)
        elif days <= 7:
            groups["THIS WEEK"].append(entry)
        else:
            groups["FRESH"].append(entry)

    # Sort each group by days ascending (most urgent first within group)
    for key in groups:
        groups[key].sort(key=lambda x: x[1])

    return groups


# ---------------------------------------------------------------------------
# Image renderer
# ---------------------------------------------------------------------------
# Layout constants
MARGIN_X      = 24   # left/right page margin
MARGIN_TOP    = 16   # top margin
TITLE_H       = 48   # height reserved for the main title
SECTION_H     = 32   # height of a section header row
ITEM_H        = 28   # height of an item row
FOOTER_H      = 24   # height of the footer line
COL_DAYS_X    = 560  # x-position for the days-remaining column

# Maximum items we will render before truncating (keeps layout from overflowing)
MAX_ITEMS = 14


def _days_label(days: int) -> str:
    if days < 0:
        n = abs(days)
        return f"expired {n} day{'s' if n != 1 else ''} ago"
    if days == 0:
        return "expires today"
    return f"{days} day{'s' if days != 1 else ''}"


def render_image(items: list[dict]) -> Image.Image:
    """
    Build and return a PIL Image (mode '1', 800x480) representing the
    current produce status.  White background, black text — suitable for
    direct use with the Waveshare black/white e-paper display.
    """
    img  = Image.new("1", (WIDTH, HEIGHT), 1)  # 1 = white background
    draw = ImageDraw.Draw(img)

    groups = _group_items(items)

    y = MARGIN_TOP

    # --- Title ---
    draw.text((MARGIN_X, y), "FRESH PRODUCE", font=FONT_TITLE, fill=0)
    y += TITLE_H

    # Thin horizontal rule under the title
    draw.line([(MARGIN_X, y - 4), (WIDTH - MARGIN_X, y - 4)], fill=0, width=2)

    # --- Sections ---
    total_rendered = 0
    for section_name, entries in groups.items():
        if not entries:
            continue

        # Check if we have room for the section header + at least one item
        remaining_height = HEIGHT - FOOTER_H - y
        if remaining_height < SECTION_H + ITEM_H:
            break  # no space left

        # Section header with filled background bar
        draw.rectangle([(MARGIN_X, y), (WIDTH - MARGIN_X, y + SECTION_H - 2)], fill=0)
        draw.text((MARGIN_X + 6, y + 4), section_name, font=FONT_SECTION, fill=1)
        y += SECTION_H

        for name, days in entries:
            if total_rendered >= MAX_ITEMS:
                # Indicate truncation
                draw.text((MARGIN_X + 8, y), "  … more items …", font=FONT_SMALL, fill=0)
                y += ITEM_H
                break

            row_bottom = y + ITEM_H
            if row_bottom + FOOTER_H > HEIGHT:
                draw.text((MARGIN_X + 8, y), "  … more items …", font=FONT_SMALL, fill=0)
                y += ITEM_H
                break

            # Item name (truncate long names)
            display_name = name if len(name) <= 22 else name[:20] + "…"
            draw.text((MARGIN_X + 8, y + 2), display_name, font=FONT_ITEM, fill=0)

            # Days label right-aligned relative to COL_DAYS_X
            label = _days_label(days)
            draw.text((COL_DAYS_X, y + 2), label, font=FONT_ITEM, fill=0)

            y += ITEM_H
            total_rendered += 1

        # Small gap between sections
        y += 4

    # --- Footer ---
    now_str = datetime.now().strftime("Last updated: %d %b %Y %H:%M")
    draw.line([(MARGIN_X, HEIGHT - FOOTER_H - 4), (WIDTH - MARGIN_X, HEIGHT - FOOTER_H - 4)], fill=0, width=1)
    draw.text((MARGIN_X, HEIGHT - FOOTER_H), now_str, font=FONT_SMALL, fill=0)

    return img


# ---------------------------------------------------------------------------
# Hardware push
# ---------------------------------------------------------------------------

def push_to_display(img: Image.Image) -> None:
    """Send the rendered image to the Waveshare e-paper display."""
    if DEV_MODE:
        img.save(PREVIEW_PATH)
        print(f"[display] Dev mode — saved preview to {PREVIEW_PATH}")
        return

    epd = epd_driver.EPD()
    try:
        epd.init()
        # Convert PIL '1' image to the buffer format the Waveshare driver expects.
        # The driver's getbuffer() method accepts an RGB/L image; convert accordingly.
        epd.display(epd.getbuffer(img.convert("L")))
        epd.sleep()
        print("[display] E-paper display updated and put to sleep.")
    except Exception as exc:
        print(f"[display] ERROR updating e-paper: {exc}")
        raise
    finally:
        epd_driver.epdconfig.module_exit(cleanup=True)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def refresh_display(items: list[dict]) -> None:
    """Render the current items list and push to e-paper (or save preview)."""
    img = render_image(items)
    push_to_display(img)


# ---------------------------------------------------------------------------
# CLI usage: python display.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    from datetime import timedelta
    today = date.today()

    # Quick smoke-test with dummy data
    sample = [
        {"name": "Spinach",      "expiry_date": str(today + timedelta(days=1))},
        {"name": "Strawberries", "expiry_date": str(today)},
        {"name": "Avocados",     "expiry_date": str(today + timedelta(days=4))},
        {"name": "Tomatoes",     "expiry_date": str(today + timedelta(days=6))},
        {"name": "Carrots",      "expiry_date": str(today + timedelta(days=12))},
        {"name": "Potatoes",     "expiry_date": str(today + timedelta(days=28))},
    ]
    refresh_display(sample)
