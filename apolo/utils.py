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


COMPOUND_ARTISTS = {
    "ac/dc",
    "tyler, the creator",
    "coheed and cambria",
    "belle and sebastian",
    "portugal. the man",
    "alvin and the chipmunks",
    "angus & julia stone",
    "death from above 1979",
    "godspeed you! black emperor",
    "earth, wind & fire",
    "simon & garfunkel",
    "florence and the machine",
    "florence + the machine",
    "crosby, stills, nash & young",
    "crosby, stills & nash",
    "emerson, lake & palmer",
    "blood, sweat & tears",
    "kool & the gang",
    "above & beyond",
    "mumford & sons",
    "hall & oates",
    "brooks & dunn",
    "huey lewis & the news",
    "huey lewis and the news",
    "of monsters and men",
    "me first and the gimme gimmes",
    "the mamas & the papas",
    "the mamas and the papas",
    "tom petty and the heartbreakers",
    "tom petty & the heartbreakers",
    "king gizzard & the lizard wizard",
    "king gizzard and the lizard wizard",
    "nick cave & the bad seeds",
    "nick cave and the bad seeds",
    "marina and the diamonds",
    "marina & the diamonds",
    "iron & wine",
    "armand van helden",
    "sly & the family stone",
    "sly and the family stone",
    "bob marley & the wailers",
    "bob marley and the wailers",
    "echo & the bunnymen",
    "joan jett & the blackhearts",
    "joan jett and the blackhearts",
    "kc & the sunshine band",
    "kc and the sunshine band",
    "toots & the maytals",
    "toots and the maytals",
    "captain & tennille",
    "peaches & herb",
    "ziggy marley and the melody makers",
    "ziggy marley & the melody makers",
    "daryl hall & john oates",
    "daryl hall and john oates",
    "gladys knight & the pips",
    "gladys knight and the pips",
    "frankie lymon & the teenagers",
    "frankie lymon and the teenagers",
    "grandmaster flash & the furious five",
    "grandmaster flash and the furious five",
    "siouxsie and the banshees",
    "siouxsie & the banshees",
    "chubby checker and the fat boys",
    "chubby checker & the fat boys",
    "boyce & hart",
    "sam & dave",
    "dr. hook & the medicine show",
    "dr. hook and the medicine show",
    "commander cody and his lost planet airmen",
}


def _split_sub_artists(text: str) -> list[str]:
    """Splits multiple artists connected by &, and, commas, slashes, semicolons, x, vs, unless compound band name."""
    if not text:
        return []
    clean_text = text.strip()
    if clean_text.lower() in COMPOUND_ARTISTS:
        return [clean_text]
    split_pattern = r"(?:,\s*|\s*;\s*|\s+&\s+|\s+and\s+|\s+x\s+|\s+vs\.?\s+|\s+/\s+)"
    parts = [p.strip() for p in re.split(split_pattern, clean_text, flags=re.IGNORECASE) if p.strip()]
    return parts


def parse_artists(
    raw_artist: Optional[str],
    title: Optional[str] = None,
) -> Tuple[list[str], list[str], list[str], str]:
    """
    Parses an artist string and optional title to separate main artists from featured/guest artists.
    Returns:
      (main_artists, featured_artists, all_artists, formatted_display_artist)
    """
    if not raw_artist and not title:
        return [], [], [], "Unknown Artist"

    raw_artist_clean = (raw_artist or "").strip()
    featured_from_title: list[str] = []

    # 1. Extract featured artists from title (e.g. "Song (feat. Artist B & Artist C)")
    if title:
        feat_title_pattern = r"[\(\[]\s*(?:feat\.?|ft\.?|featuring|with)\s+([^)\]]+)[\)\]]"
        match = re.search(feat_title_pattern, title, flags=re.IGNORECASE)
        if match:
            raw_feat = match.group(1).strip()
            featured_from_title.extend(_split_sub_artists(raw_feat))

    # 2. Check compound artist match before splitting
    if raw_artist_clean.lower() in COMPOUND_ARTISTS:
        main_artists = [raw_artist_clean]
        featured_artists = [f for f in featured_from_title if f.lower() != raw_artist_clean.lower()]
        all_artists = [raw_artist_clean] + [f for f in featured_artists if f not in [raw_artist_clean]]
        if featured_artists:
            feat_str = " & ".join(featured_artists) if len(featured_artists) <= 2 else ", ".join(featured_artists)
            display_str = f"{raw_artist_clean} feat. {feat_str}"
        else:
            display_str = raw_artist_clean
        return main_artists, featured_artists, all_artists, display_str

    # 3. Check if raw_artist has featured indicators
    feat_artist_pattern = r"\s+(?:feat\.?|ft\.?|featuring|with|pres\.?)\s+"
    parts = re.split(feat_artist_pattern, raw_artist_clean, maxsplit=1, flags=re.IGNORECASE)

    main_artists = []
    featured_artists = []

    if len(parts) == 2:
        main_part, feat_part = parts
        main_artists.extend(_split_sub_artists(main_part))
        featured_artists.extend(_split_sub_artists(feat_part))
    elif raw_artist_clean:
        main_artists.extend(_split_sub_artists(raw_artist_clean))

    # Add featured from title
    for f in featured_from_title:
        if f not in featured_artists and f not in main_artists:
            featured_artists.append(f)

    # Clean duplicates while preserving order
    all_artists: list[str] = []
    seen = set()
    for a in main_artists + featured_artists:
        norm = a.lower()
        if norm not in seen:
            seen.add(norm)
            all_artists.append(a)

    # Format display string
    if not main_artists and not featured_artists:
        display_str = raw_artist_clean or "Unknown Artist"
    elif featured_artists:
        main_str = " & ".join(main_artists) if len(main_artists) <= 2 else ", ".join(main_artists)
        feat_str = " & ".join(featured_artists) if len(featured_artists) <= 2 else ", ".join(featured_artists)
        if main_str:
            display_str = f"{main_str} feat. {feat_str}"
        else:
            display_str = feat_str
    else:
        display_str = raw_artist_clean or (" & ".join(main_artists) if len(main_artists) <= 2 else ", ".join(main_artists))

    return main_artists, featured_artists, all_artists, display_str


def extract_primary_artist(artist_str: Optional[str]) -> Optional[str]:
    """Extract first main artist before commas, feat, ft., vs, x."""
    if not artist_str:
        return None
    main_artists, _, all_artists, _ = parse_artists(artist_str)
    if main_artists:
        return main_artists[0]
    if all_artists:
        return all_artists[0]
    return artist_str.strip()


def infer_consensus_album_artist(tracks: list, threshold: float = 0.70) -> Optional[str]:
    """
    Infers the consensus album artist for a collection of tracks from the same album.
    If a primary artist accounts for >= threshold (default 70%) of tracks (minimum 2 tracks),
    that artist is returned as the consensus album artist.
    """
    if not tracks or len(tracks) < 2:
        return None

    primary_artists: list[str] = []
    for t in tracks:
        if isinstance(t, dict):
            raw_art = t.get("album_artist") or t.get("artist")
        else:
            raw_art = getattr(t, "album_artist", None) or getattr(t, "artist", None)

        prim = extract_primary_artist(raw_art)
        if prim:
            primary_artists.append(prim)

    if not primary_artists or len(primary_artists) < 2:
        return None

    from collections import Counter
    counts = Counter(primary_artists)
    top_artist, top_count = counts.most_common(1)[0]

    if (top_count / len(tracks)) >= threshold:
        return top_artist

    return None


def infer_consensus_date(tracks: list, threshold: float = 0.50) -> Optional[str]:
    """
    Infers the consensus release date/year for a collection of tracks from the same album.
    """
    if not tracks:
        return None

    dates: list[str] = []
    for t in tracks:
        if isinstance(t, dict):
            d = t.get("date")
        else:
            d = getattr(t, "date", None)
        if d:
            dates.append(str(d).strip())

    if not dates:
        return None

    from collections import Counter
    counts = Counter(dates)
    top_date, top_count = counts.most_common(1)[0]
    if (top_count / len(dates)) >= threshold:
        return top_date

    # If full dates differ (e.g. YYYY-MM-DD), check consensus by Year
    years: list[str] = []
    for d in dates:
        match = re.search(r"\b(19\d{2}|20\d{2})\b", d)
        if match:
            years.append(match.group(1))
    if years:
        year_counts = Counter(years)
        top_year, top_year_count = year_counts.most_common(1)[0]
        if (top_year_count / len(years)) >= threshold:
            return top_year

    return dates[0]


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


def is_compilation_album(album_title: Optional[str], album_artist: Optional[str] = None) -> bool:
    """Determines if the album is a compilation / Various Artists release."""
    if album_artist:
        norm_aa = album_artist.strip().lower()
        if norm_aa in ["various artists", "various", "v.a.", "v. a.", "varios artistas", "varios"]:
            return True
        # If album_artist is explicitly specified and not a generic VA tag, it is a single-artist/composer album
        if norm_aa not in ["soundtrack", "ost", "original soundtrack"]:
            return False

    if album_title:
        norm_title = album_title.strip().lower()
        # Only classify by title if the title explicitly mentions Various Artists or V.A.
        compilation_patterns = [
            r"\bvarious artists\b",
            r"\bvarios artistas\b",
            r"\bv\.a\.\b",
        ]
        if any(re.search(pat, norm_title) for pat in compilation_patterns):
            return True

    return False


def is_single_release(album_title: Optional[str], track_total: Optional[int]) -> bool:
    """Determines if a release is a single."""
    if not album_title or album_title.strip().lower() in ["single", "singles", "unknown album"]:
        return True

    norm_album = album_title.strip().lower()
    is_single_naming = bool(
        re.search(r"(\s*-\s*single|\s*\(\s*single\s*\)|\s*\[\s*single\s*\])$", norm_album)
        or norm_album in ["single", "singles"]
    )
    if is_single_naming and (track_total is None or track_total <= 3):
        return True

    if track_total is not None and track_total <= 2 and "single" in norm_album:
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
