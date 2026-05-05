"""
generate_app_icons.py
---------------------
Generates iPhone-quality PWA app icons from the Fluid Notes logo.

Outputs to dashboard/static/icons/:
  icon-180.png  — apple-touch-icon (primary iOS Home Screen icon)
  icon-192.png  — PWA manifest / Android
  icon-512.png  — PWA manifest splash / install prompt

Design spec:
  • 1024×1024 master canvas → downsampled with high-quality Lanczos
  • Background: radial gradient matching the app's dark navy palette
  • Logo (transparent version): centred, scaled to 82% of the canvas so
    there is visible breathing room from the edges (iOS clips to a
    superellipse so content near the edges gets masked anyway)
  • No rounded corners are added here — iOS applies the superellipse mask
    automatically; providing a flat square is the correct approach
"""

import math
from pathlib import Path
from PIL import Image, ImageDraw

BASE_DIR = Path(__file__).resolve().parent.parent
LOGO_PATH = BASE_DIR / "dashboard" / "static" / "dashboard" / "images" / "fluid_notes_logo_1_transparent.png"
OUT_DIR   = BASE_DIR / "dashboard" / "static" / "icons"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MASTER_SIZE = 1024          # work at 1024 then downsample
LOGO_SCALE  = 0.82          # logo occupies 82% of the canvas width/height

# App background colours (replicating the radial gradient coarsely with a solid)
BG_CENTRE  = (11, 35, 56)   # #0B2338
BG_EDGE    = (5,  13, 24)   # #050D18


def make_radial_bg(size: int) -> Image.Image:
    """Create a square image with a simple radial dark-navy gradient."""
    img = Image.new("RGBA", (size, size), BG_EDGE)
    draw = ImageDraw.Draw(img)
    cx, cy = size * 0.20, size * 0.10   # gradient centre (matches CSS)
    max_r = math.hypot(size, size)

    for y in range(size):
        for x in range(size):
            dist = math.hypot(x - cx, y - cy) / max_r
            t = min(dist * 1.6, 1.0)
            r = int(BG_CENTRE[0] + (BG_EDGE[0] - BG_CENTRE[0]) * t)
            g = int(BG_CENTRE[1] + (BG_EDGE[1] - BG_CENTRE[1]) * t)
            b = int(BG_CENTRE[2] + (BG_EDGE[2] - BG_CENTRE[2]) * t)
            draw.point((x, y), fill=(r, g, b, 255))
    return img


def generate_icon(size: int, out_name: str) -> None:
    print(f"  Generating {out_name} ({size}×{size}) …", end=" ", flush=True)

    # --- 1. Build master gradient background ---
    canvas = make_radial_bg(MASTER_SIZE)

    # --- 2. Load & resize logo to 82% of master canvas ---
    logo_raw = Image.open(LOGO_PATH).convert("RGBA")
    logo_size = int(MASTER_SIZE * LOGO_SCALE)
    logo = logo_raw.resize((logo_size, logo_size), Image.LANCZOS)

    # --- 3. Centre-paste logo onto background (preserving alpha) ---
    offset = (MASTER_SIZE - logo_size) // 2
    canvas.paste(logo, (offset, offset), logo)

    # --- 4. Downsample to target size with Lanczos for crisp edges ---
    if size < MASTER_SIZE:
        final = canvas.resize((size, size), Image.LANCZOS)
    else:
        final = canvas

    final = final.convert("RGB")   # strip alpha — PWA icons must be opaque
    out_path = OUT_DIR / out_name
    final.save(out_path, "PNG", optimize=True, compress_level=6)
    print(f"saved → {out_path.relative_to(BASE_DIR)}")


if __name__ == "__main__":
    print("Fluid Notes — app icon generator")
    print(f"  Source logo : {LOGO_PATH.relative_to(BASE_DIR)}")
    print(f"  Output dir  : {OUT_DIR.relative_to(BASE_DIR)}")
    print()

    generate_icon(180, "icon-180.png")
    generate_icon(192, "icon-192.png")
    generate_icon(512, "icon-512.png")

    print("\nDone. All icons written successfully.")
