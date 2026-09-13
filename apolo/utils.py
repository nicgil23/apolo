import re
import unicodedata
from typing import Optional, Tuple


def normalize_search_string(text: str) -> str:
    """Normalize text by removing emojis and punctuation noise while preserving all international characters and combining marks."""
    if not text:
        return ""
    # NFKC normalization converts fullwidth characters and precomposes combining marks
    normalized = unicodedata.normalize("NFKC", text)
    result = []
    for ch in normalized:
        cat = unicodedata.category(ch)
        if cat.startswith(("L", "N", "M")) or ch in " -\t\n\r":
            result.append(ch)
        else:
            result.append(" ")
    cleaned = "".join(result)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def sanitize_filename(name: str, replace_char: str = "_", max_chars: int = 180) -> str:
    """
    Sanitize a string to be safely used as a filename or directory name,
    ensuring it does not exceed OS filesystem byte/length limits.
    """
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

    if not cleaned:
        return "Unknown"

    # Truncate if exceeds max_chars safely
    if len(cleaned.encode("utf-8")) > max_chars:
        while len(cleaned.encode("utf-8")) > max_chars:
            cleaned = cleaned[:-1]
        cleaned = cleaned.strip(". _")

    return cleaned or "Unknown"


def clean_track_title(raw_title: str) -> Tuple[str, Optional[str]]:
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
    split_pattern = r"(?:,\s*|\s+(?:feat\.?|ft\.?|x|vs\.?|&)\s+)"
    parts = re.split(split_pattern, artist_str, flags=re.IGNORECASE)
    if parts:
        return parts[0].strip()
    return artist_str.strip()


def extract_disc_info(text: Optional[str]) -> Tuple[str, Optional[int]]:
    """
    Extracts disc number if present in album/title string, e.g.
    'The Wall (Disc 2)' -> ('The Wall', 2)
    'Stadium Arcadium [CD 1]' -> ('Stadium Arcadium', 1)
    'Final Fantasy VII OST (Vol. 3)' -> ('Final Fantasy VII OST', 3)
    """
    if not text:
        return "", None

    pattern = r"\s*[\(\[]\s*(?:disc|cd|vol(?:ume)?|part|pt\.?)\s*(\d+)\s*[\)\]]"
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if match:
        disc_num = int(match.group(1))
        cleaned_text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
        return cleaned_text or text, disc_num

    return text, None


def is_compilation_album(album_title: Optional[str], album_artist: Optional[str]) -> bool:
    """Determines if the album is a compilation / Various Artists release."""
    if album_artist:
        norm_aa = album_artist.strip().lower()
        if norm_aa in ["various artists", "various", "v.a.", "varios artistas", "soundtrack", "ost"]:
            return True

    if album_title:
        norm_title = album_title.strip().lower()
        # Use word-boundary regex to prevent false positives (e.g., 'ost' in 'nostalgia' or 'ghost')
        compilation_patterns = [
            r"\boriginal soundtrack\b",
            r"\bmotion picture soundtrack\b",
            r"\bsoundtrack\b",
            r"\bost\b",
            r"\bvarious artists\b",
            r"\bv\.a\.\b",
        ]
        if any(re.search(pat, norm_title) for pat in compilation_patterns):
            return True

    return False


def is_single_release(album_title: Optional[str], track_total: Optional[int]) -> bool:
    """Determines if a release is a single."""
    if not album_title or album_title.strip().lower() in ["single", "singles", "unknown album"]:
        return True
    if track_total is not None and track_total <= 2 and "single" in album_title.lower():
        return True
    return False


def format_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "00:00"
    total_seconds = int(seconds)
    mins = total_seconds // 60
    secs = total_seconds % 60
    return f"{mins:02d}:{secs:02d}"


def clean_media_url(url: str) -> str:
    """
    Cleans tracking, radio lists (list=RD...), and noise parameters from URLs.
    If a URL points to a specific video (e.g. watch?v=... or youtu.be/...),
    it strips radio/mix playlist parameters to avoid downloading infinite radio queues.
    """
    if not url:
        return ""

    from urllib.parse import parse_qs, urlparse, urlunparse

    parsed = urlparse(url.strip())
    netloc = parsed.netloc.lower()

    # YouTube / YouTube Music
    if "youtube.com" in netloc or "youtu.be" in netloc:
        query_params = parse_qs(parsed.query)

        # If it's a watch URL or has a 'v' parameter
        if "v" in query_params:
            video_id = query_params["v"][0]
            clean_query = f"v={video_id}"
            scheme = parsed.scheme or "https"
            return urlunparse((scheme, parsed.netloc, parsed.path, "", clean_query, ""))

        # If it's youtu.be/VIDEO_ID
        if "youtu.be" in netloc and parsed.path.strip("/"):
            video_id = parsed.path.strip("/").split("/")[0]
            return f"https://youtu.be/{video_id}"

        # If it's an explicit playlist page: /playlist?list=...
        if "/playlist" in parsed.path and "list" in query_params:
            list_id = query_params["list"][0]
            scheme = parsed.scheme or "https"
            return urlunparse((scheme, parsed.netloc, "/playlist", "", f"list={list_id}", ""))

    return url.strip()
