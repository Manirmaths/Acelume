"""
Regenerate the Acelume raster icons from the same geometry as the SVG mark.

Source of truth for the mark is `frontend/public/favicon.svg` and the inline
copy in `frontend/src/components/ui/Logo.tsx`. This script reproduces that
geometry in Pillow so the PWA/apple-touch PNGs cannot drift from the SVG.

If you change the mark, change all three: favicon.svg, Logo.tsx, and the
coordinates below -- then re-run this.

    python tools/generate_icons.py

Outputs (relative to frontend/public/icons/):
    icon-192.png            PWA manifest
    icon-512.png            PWA manifest + Play Store source
    apple-touch-icon.png    iOS home screen (180x180)

NOT handled here: the Android launcher icons under
`frontend/android/app/src/main/res/mipmap-*/`. Those use adaptive-icon
foreground/background layers with a 66% safe zone, and getting them wrong
looks worse than leaving them. Regenerate those from Android Studio's Image
Asset tool (right-click res -> New -> Image Asset) using icon-512.png as the
source, at the same time as the next app rebuild.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "frontend" / "public" / "icons"
SS = 4  # supersample factor; downsampled with LANCZOS for clean edges

GRAD_FROM = (0x4F, 0x46, 0xE5)
GRAD_TO = (0x3B, 0x32, 0xC9)


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))  # type: ignore[return-value]


def render(px: int) -> Image.Image:
    size = px * SS
    k = size / 512.0  # everything below is in the SVG's 512x512 coordinate space
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))

    # Diagonal gradient, clipped to the outer rounded square.
    grad = Image.new("RGB", (size, size))
    gd = ImageDraw.Draw(grad)
    for i in range(2 * size):
        gd.line([(i, 0), (0, i)], fill=_lerp(GRAD_FROM, GRAD_TO, i / (2 * size - 1)))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((24 * k, 24 * k, 488 * k, 488 * k), radius=int(124 * k), fill=255)
    img.paste(grad, (0, 0), mask)

    # Inner lighter panel (matches fill-opacity 0.07 in the SVG).
    panel = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(panel).rounded_rectangle(
        (80 * k, 80 * k, 432 * k, 432 * k), radius=int(96 * k), fill=(255, 255, 255, 18)
    )
    img.alpha_composite(panel)

    # The "A": semicircular arch, two straight legs, one crossbar.
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w = 34 * k
    stroke = int(round(w))
    cx, cy, r = 256 * k, 255 * k, 75 * k
    white = (255, 255, 255, 255)
    d.arc([cx - r - w / 2, cy - r - w / 2, cx + r + w / 2, cy + r + w / 2], 180, 360, fill=white, width=stroke)
    d.line([(cx - r, cy), (cx - r, 372 * k)], fill=white, width=stroke)
    d.line([(cx + r, cy), (cx + r, 372 * k)], fill=white, width=stroke)
    d.line([(cx - r - w / 2, 310 * k), (cx + r + w / 2, 310 * k)], fill=white, width=stroke)
    img.alpha_composite(layer)

    return img.resize((px, px), Image.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for px, name in ((192, "icon-192.png"), (512, "icon-512.png"), (180, "apple-touch-icon.png")):
        path = OUT / name
        render(px).save(path)
        print(f"wrote {path.relative_to(OUT.parent.parent.parent)}")


if __name__ == "__main__":
    main()
