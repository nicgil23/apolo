import re
from typing import Optional, Tuple

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
