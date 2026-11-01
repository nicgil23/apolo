import re
import unicodedata
from urllib.parse import parse_qs, urlparse, urlunparse

from apolo.metadata.heuristics import (
    infer_consensus_album_artist,
    infer_consensus_date,
    is_compilation_album,
    is_single_release,
)
from apolo.metadata.parsing import (
    clean_track_title,
    extract_disc_info,
    extract_primary_artist,
    parse_artists,
)
from apolo.storage.sanitize import (
    UNICODE_FS_REPLACEMENTS,
    normalize_dir_key,
    sanitize_filename,
    strip_accents,
)


def normalize_search_string(text: str) -> str:
    """Normalize text by removing emojis and punctuation noise while preserving international characters."""
    if not text:
        return ""
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
    cleaned = cleaned.strip()
    if not cleaned and text.strip():
        fallback = "".join(ch for ch in text if unicodedata.category(ch) != "Cc").strip()
        return fallback or text.strip()
    return cleaned


def format_duration(seconds: float | int | None) -> str:
    """Format duration in seconds as MM:SS."""
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
    For playlists and albums, it normalizes to standard YouTube playlist format.
    """
    if not url:
        return ""

    parsed = urlparse(url.strip())
    netloc = parsed.netloc.lower()

    # YouTube / YouTube Music
    if "youtube.com" in netloc or "youtu.be" in netloc:
        query_params = parse_qs(parsed.query)

        # If it's a watch URL or has a 'v' parameter (single track)
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
        if "list" in query_params:
            list_id = query_params["list"][0]
            return f"https://www.youtube.com/playlist?list={list_id}"

        # If it's a YouTube Music /browse URL with VL playlist ID
        if "/browse" in parsed.path:
            path_clean = parsed.path.strip("/")
            if "VL" in path_clean:
                list_id = path_clean.split("VL", 1)[1]
                return f"https://www.youtube.com/playlist?list={list_id}"

    return url.strip()


__all__ = [
    "normalize_search_string",
    "format_duration",
    "clean_media_url",
    "strip_accents",
    "normalize_dir_key",
    "UNICODE_FS_REPLACEMENTS",
    "sanitize_filename",
    "clean_track_title",
    "parse_artists",
    "extract_primary_artist",
    "extract_disc_info",
    "infer_consensus_album_artist",
    "infer_consensus_date",
    "is_compilation_album",
    "is_single_release",
]
