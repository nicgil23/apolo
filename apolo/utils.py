import re
import unicodedata


def normalize_search_string(text: str) -> str:
    """Normalize text by removing emojis, fullwidth chars, and punctuation noise."""
    if not text:
        return ""
    # NFKD normalization to convert fullwidth characters (e.g. ： to :, ＂ to ")
    normalized = unicodedata.normalize("NFKD", text)
    # Remove emojis and non-alphanumeric except basic spacing
    cleaned = re.sub(r"[^\w\s-]", " ", normalized)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def sanitize_filename(name: str, replace_char: str = "_") -> str:
    """Sanitize a string to be safely used as a filename or directory name."""
    if not name:
        return "Unknown"
    # Replace illegal characters
    cleaned = re.sub(r'[\\/*?:"<>|]+', replace_char, name)
    # Remove control characters
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", cleaned)
    # Replace multiple spaces/underscores
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned)
    cleaned = cleaned.strip(". _")
    return cleaned or "Unknown"


def clean_track_title(raw_title: str) -> tuple[str, str | None]:
    """
    Attempt to extract (title, artist) or cleaned title from video titles like:
    - 'Artist - Song Title (Official Music Video)' -> ('Song Title', 'Artist')
    - 'Artist - Song Title [Lyrics]' -> ('Song Title', 'Artist')
    """
    cleaned = raw_title
    # Remove common youtube noise patterns in parentheses or brackets
    noise_patterns = [
        r"\s*[\(\[][^)\]]*(official|video|audio|visualizer|lyric|remaster|hd|4k|hq|letra|videoclip|premiere)[^)\]]*[\)\]]",
    ]
    for pattern in noise_patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    cleaned = cleaned.strip()

    # Check for 'Artist - Title' separator
    if " - " in cleaned:
        parts = cleaned.split(" - ", 1)
        artist_part = parts[0].strip()
        title_part = parts[1].strip()
        return title_part, artist_part

    return cleaned, None


def extract_primary_artist(artist_str: Optional[str]) -> Optional[str]:
    """Extract first main artist before commas, feat, ft., vs, x."""
    if not artist_str:
        return None
    # Split by separators
    split_pattern = r"(?:,\s*|\s+(?:feat\.?|ft\.?|x|vs\.?|&)\s+)"
    parts = re.split(split_pattern, artist_str, flags=re.IGNORECASE)
    if parts:
        return parts[0].strip()
    return artist_str.strip()


def format_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "00:00"
    total_seconds = int(seconds)
    mins = total_seconds // 60
    secs = total_seconds % 60
    return f"{mins:02d}:{secs:02d}"
