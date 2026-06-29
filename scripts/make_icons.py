"""Generate platform icons from the Pixilart source art.

Reads ``assets/Cigliet.pixil``, trims the transparent margins, centers the art on
a square canvas, and writes:

  * ``assets/icon.png``   256x256   - runtime window / taskbar / dock icon
  * ``assets/icon.ico``   multi-size - Windows executable icon
  * ``assets/icon.icns``  multi-size - macOS .app bundle icon

Re-run after editing the artwork:  ``python scripts/make_icons.py``
Requires Pillow (in requirements-dev.txt).
"""

from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SRC = ASSETS / "Cigliet.pixil"


def load_pixil(path: Path) -> Image.Image:
    """Composite all layers of the first frame into one RGBA image."""
    data = json.loads(path.read_text(encoding="utf-8"))
    base: Image.Image | None = None
    for layer in data["frames"][0]["layers"]:
        uri = layer.get("src", "")
        if "," not in uri:
            continue
        # The data-URI prefix is mangled by Pixilart, but the base64 payload
        # after the first comma is a valid PNG and contains no commas.
        raw = base64.b64decode(uri.split(",", 1)[1])
        layer_img = Image.open(io.BytesIO(raw)).convert("RGBA")
        base = layer_img if base is None else Image.alpha_composite(base, layer_img)
    if base is None:
        raise SystemExit(f"No embedded image data found in {path}")
    return base


def square_centered(img: Image.Image, pad_ratio: float = 0.14) -> Image.Image:
    """Crop transparent margins, then center the art on a padded square canvas."""
    bbox = img.getbbox()
    if bbox is None:
        raise SystemExit("Source artwork is fully transparent")
    content = img.crop(bbox)
    w, h = content.size
    side = int(round(max(w, h) * (1 + 2 * pad_ratio)))
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(content, ((side - w) // 2, (side - h) // 2))
    return canvas


def main() -> None:
    art = load_pixil(SRC)
    base = square_centered(art)
    # Nearest-neighbour upscale keeps the pixel-art edges crisp at large sizes.
    master = base.resize((1024, 1024), Image.NEAREST)

    ASSETS.mkdir(exist_ok=True)
    master.resize((256, 256), Image.NEAREST).save(ASSETS / "icon.png")
    master.save(
        ASSETS / "icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    master.save(ASSETS / "icon.icns")
    print(f"Wrote icon.png, icon.ico, icon.icns to {ASSETS}")


if __name__ == "__main__":
    main()
