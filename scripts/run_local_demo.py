"""Run the image steps on a generated file and write the before/after samples."""

import sys
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "image"))

from process import apply_watermark, inspect_image, resize_image


def main():
    out_dir = ROOT / "docs" / "samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    original = _sample_image()
    (out_dir / "original.png").write_bytes(original)
    display = resize_image(original, 1280)
    thumbnail = resize_image(original, 300)
    processed = apply_watermark(display, "PREVIEW")
    (out_dir / "display.png").write_bytes(processed)
    (out_dir / "thumbnail.png").write_bytes(apply_watermark(thumbnail, "PREVIEW"))
    before = inspect_image(original)
    after = inspect_image(processed)
    print(f"original {before['width']}x{before['height']}")
    print(f"display  {after['width']}x{after['height']}")


def _sample_image() -> bytes:
    image = Image.new("RGB", (1600, 900), (18, 84, 140))
    draw = ImageDraw.Draw(image)
    draw.rectangle((80, 80, 1520, 820), outline=(255, 196, 60), width=16)
    draw.ellipse((180, 180, 620, 620), fill=(232, 96, 58))
    draw.rectangle((760, 260, 1420, 640), fill=(246, 241, 230))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


if __name__ == "__main__":
    main()
