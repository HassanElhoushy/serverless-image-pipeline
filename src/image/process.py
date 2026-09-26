import io

from PIL import Image, ImageDraw, ImageFont, ImageOps

MAX_BYTES = 10 * 1024 * 1024
ACCEPTED_FORMATS = {"JPEG", "PNG", "WEBP"}
FONT_CANDIDATES = (
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
)


class InvalidImage(ValueError):
    pass


def inspect_image(data: bytes, limit: int = MAX_BYTES) -> dict:
    if not data:
        raise InvalidImage("file is empty")
    if len(data) > limit:
        raise InvalidImage("file exceeds 10 MB")
    try:
        with Image.open(io.BytesIO(data)) as img:
            image_format = (img.format or "").upper()
            img = ImageOps.exif_transpose(img)
            img.load()
            width, height = img.size
    except InvalidImage:
        raise
    except Exception as exc:
        raise InvalidImage("file is not a readable image") from exc
    if image_format not in ACCEPTED_FORMATS:
        raise InvalidImage(f"unsupported format: {image_format or 'unknown'}")
    if width < 1 or height < 1:
        raise InvalidImage("image dimensions are invalid")
    return {"width": width, "height": height, "format": image_format, "bytes": len(data)}


def resize_image(data: bytes, max_edge: int) -> bytes:
    with Image.open(io.BytesIO(data)) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        return _png_bytes(img)


def apply_watermark(data: bytes, text: str) -> bytes:
    with Image.open(io.BytesIO(data)) as img:
        base = ImageOps.exif_transpose(img).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = _font(max(16, base.width // 28))
    label = text.strip() or "PREVIEW"
    left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
    text_width = right - left
    text_height = bottom - top
    margin = max(12, base.width // 40)
    x = max(margin, base.width - text_width - margin)
    y = max(margin, base.height - text_height - margin)
    draw.rectangle(
        (x - 10, y - 8, x + text_width + 10, y + text_height + 8),
        fill=(0, 0, 0, 120),
    )
    draw.text((x, y), label, font=font, fill=(255, 255, 255, 230))
    flattened = Image.alpha_composite(base, overlay).convert("RGB")
    return _png_bytes(flattened)


def _png_bytes(img: Image.Image) -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _font(size: int) -> ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()
