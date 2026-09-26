import re

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
}


def safe_file_name(name: str) -> str:
    base = (name or "").replace("\\", "/").split("/")[-1].strip()
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    base = base.strip("._") or "image"
    return base[:80]


def resolve_content_type(file_name: str, content_type: str) -> str:
    requested = (content_type or "").split(";")[0].strip().lower()
    extension = "." + file_name.lower().rsplit(".", 1)[-1] if "." in file_name else ""
    if requested in ALLOWED_CONTENT_TYPES:
        if extension and extension not in ALLOWED_CONTENT_TYPES[requested]:
            raise ValueError("file extension does not match content type")
        return requested
    for candidate, extensions in ALLOWED_CONTENT_TYPES.items():
        if extension in extensions:
            return candidate
    raise ValueError("only jpeg, png, and webp images are accepted")
