import re
import unicodedata
from typing import Optional


def strip_accents(text: Optional[str]) -> str:
    """Removes diacritics / accent marks from text, returning ASCII-equivalent base characters."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def normalize_dir_key(text: Optional[str]) -> str:
    """
    Normalizes a directory name for comparison by removing diacritics/accents,
    special symbols, and excess whitespace, lowercased.
    """
    if not text:
        return ""
    clean = strip_accents(text).lower()
    clean = re.sub(r"[^\w\s]", "", clean)
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


UNICODE_FS_REPLACEMENTS = {
    "/": "／",   # Fullwidth solidus \uFF0F
    "\\": "＼",  # Fullwidth reverse solidus \uFF3C
    ":": "：",   # Fullwidth colon \uFF1A
    "*": "＊",   # Fullwidth asterisk \uFF0A
    "?": "？",   # Fullwidth question mark \uFF1F
    '"': "”",   # Right double quotation mark \u201D
    "<": "＜",   # Fullwidth less-than sign \uFF1C
    ">": "＞",   # Fullwidth greater-than sign \uFF1E
    "|": "｜",   # Fullwidth vertical line \uFF5C
}


def sanitize_filename(
    name: str,
    replace_char: Optional[str] = None,
    max_chars: int = 180,
    use_unicode: bool = True,
) -> str:
    """
    Sanitize a string to be safely used as a filename or directory name,
    ensuring it does not exceed OS filesystem byte/length limits.
    By default, maps reserved characters (:, /, ?, *, etc.) to aesthetic full-width Unicode characters.
    """
    if not name:
        return "Unknown"

    if replace_char is not None:
        cleaned = re.sub(r'[\\/*?:"<>|]+', replace_char, name)
        cleaned = re.sub(r"_+", "_", cleaned)
    elif use_unicode:
        cleaned = "".join(UNICODE_FS_REPLACEMENTS.get(ch, ch) for ch in name)
    else:
        cleaned = re.sub(r'[\\/*?:"<>|]+', "_", name)
        cleaned = re.sub(r"_+", "_", cleaned)

    # Remove control characters
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", cleaned)
    # Normalize multiple spaces
    cleaned = re.sub(r"\s+", " ", cleaned)
    strip_chars = f". {replace_char}" if replace_char else ". "
    cleaned = cleaned.strip(strip_chars)

    if not cleaned:
        return "Unknown"

    # Truncate if exceeds max_chars safely
    if len(cleaned.encode("utf-8")) > max_chars:
        while len(cleaned.encode("utf-8")) > max_chars:
            cleaned = cleaned[:-1]
        cleaned = cleaned.strip(strip_chars)

    return cleaned or "Unknown"
