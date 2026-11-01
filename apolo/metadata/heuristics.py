import re
from collections import Counter

from apolo.metadata.parsing import extract_primary_artist


def infer_consensus_album_artist(tracks: list, threshold: float = 0.50) -> str | None:
    """
    Infers the consensus album artist for a collection of tracks from the same album.
    If a primary artist accounts for >= threshold (default 50%) of tracks (minimum 2 tracks),
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

    counts = Counter(primary_artists)
    top_artist, top_count = counts.most_common(1)[0]

    if (top_count / len(tracks)) >= threshold:
        return top_artist

    return None


def infer_consensus_date(tracks: list, threshold: float = 0.50) -> str | None:
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


def is_compilation_album(album_title: str | None, album_artist: str | None = None) -> bool:
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


def is_single_release(album_title: str | None, track_total: int | None) -> bool:
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
