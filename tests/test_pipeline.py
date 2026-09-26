import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "image"))
sys.path.insert(0, str(ROOT / "src" / "api"))

from names import resolve_content_type, safe_file_name
from PIL import Image
from process import InvalidImage, apply_watermark, inspect_image, resize_image


def test_safe_file_name_strips_paths_and_unsafe_characters():
    assert safe_file_name(r"..\uploads\my photo.jpg") == "my_photo.jpg"
    assert safe_file_name("") == "image"


def test_resolve_content_type_matches_extension():
    assert resolve_content_type("photo.jpg", "image/jpeg") == "image/jpeg"
    assert resolve_content_type("photo.png", "") == "image/png"
    with pytest.raises(ValueError):
        resolve_content_type("photo.png", "image/jpeg")
    with pytest.raises(ValueError):
        resolve_content_type("notes.txt", "text/plain")


def _solid(width, height, color):
    image = Image.new("RGB", (width, height), color)
    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_inspect_accepts_png_and_rejects_garbage():
    info = inspect_image(_solid(40, 20, (10, 20, 30)))
    assert info["width"] == 40
    assert info["height"] == 20
    assert info["format"] == "PNG"
    with pytest.raises(InvalidImage):
        inspect_image(b"this is not an image")
    with pytest.raises(InvalidImage):
        inspect_image(b"")


def test_resize_limits_the_longest_edge():
    resized = resize_image(_solid(1600, 900, (20, 80, 160)), 1280)
    info = inspect_image(resized)
    assert max(info["width"], info["height"]) <= 1280
    assert info["width"] == 1280


def test_watermark_changes_the_image_bytes():
    original = resize_image(_solid(800, 500, (200, 40, 40)), 800)
    marked = apply_watermark(original, "PREVIEW")
    assert marked != original
    assert inspect_image(marked)["format"] == "PNG"
