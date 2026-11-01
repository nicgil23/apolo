import re
import unicodedata

# Canonical genre mapping from raw provider tags or multi-genre strings to normalized forms
GENRE_MAPPING: dict[str, str] = {
    # Trap & Hip-Hop / Rap
    "trap / hip-hop": "Trap",
    "trap / urbano latino": "Trap Latino",
    "urbano latino / trap": "Trap Latino",
    "trap / alternative": "Trap",
    "trap": "Trap",
    "trap latino": "Trap Latino",
    "hip-hop": "Hip-Hop",
    "hip-hop/rap": "Hip-Hop",
    "rap/hip hop": "Hip-Hop",
    "rap / hip-hop": "Hip-Hop",
    "rap": "Rap",
    "latin rap": "Rap Latino",
    "alternative rap": "Hip-Hop Alternativo",
    "alternative / hip-hop": "Hip-Hop Alternativo",
    "hip-hop alternativo": "Hip-Hop Alternativo",
    # J-Core, Hardcore & Speedcore
    "j-core / hardcore": "J-Core",
    "hardcore techno / j-core": "J-Core",
    "j-core / electronic": "J-Core",
    "electronic / j-core": "J-Core",
    "j-core / pop": "J-Core",
    "j-core / speedcore": "Speedcore",
    "electronic / speedcore": "Speedcore",
    "speedcore / terrorcore": "Speedcore",
    "hardcore techno": "Hardcore Techno",
    "frenchcore / hardcore techno": "Frenchcore",
    "hardcore techno / frenchcore": "Frenchcore",
    "frenchcore": "Frenchcore",
    "happy hardcore": "Happy Hardcore",
    "hardcore": "Hardcore",
    "j-core": "J-Core",
    "speedcore": "Speedcore",
    # Electronic, Dance & Club subgenres
    "electronic": "Electronic",
    "electro": "Electro",
    "electrónica": "Electronic",
    "electronica": "Electronic",
    "dance": "Dance",
    "dance, électronique": "Dance",
    "dance, electronique": "Dance",
    "electronic; dance; techno": "Techno",
    "techno": "Techno",
    "dubstep": "Dubstep",
    "house": "House",
    "trance": "Trance",
    "electronic / chiptune": "Chiptune",
    "chiptune": "Chiptune",
    "nightcore": "Nightcore",
    "pop electronica": "Electropop",
    "electronic / pop": "Electropop",
    "electropop": "Electropop",
    "electronic; latin": "Electronic",
    "synthwave": "Synthwave",
    "synth-pop": "Synthpop",
    "synthpop": "Synthpop",
    # Latin & Urbano
    "urbano latino": "Urbano Latino",
    "latino": "Latino",
    "latin": "Latino",
    "latin music": "Latino",
    "reggaeton": "Reggaeton",
    "pop latino": "Pop Latino",
    "música brasileña": "Música Brasileña",
    "musica brasileña": "Música Brasileña",
    "música tropical": "Música Tropical",
    "musica tropical": "Música Tropical",
    "música mexicana": "Música Mexicana",
    "musica mexicana": "Música Mexicana",
    "modern dancehall": "Dancehall",
    "dancehall": "Dancehall",
    "afrobeats": "Afrobeats",
    "música africana": "Afrobeats",
    "musica africana": "Afrobeats",
    # Pop & R&B
    "pop": "Pop",
    "alternative / pop": "Pop Alternativo",
    "pop alternativo": "Pop Alternativo",
    "r&b": "R&B",
    "r&b/soul": "R&B / Soul",
    "r&b / soul": "R&B / Soul",
    "contemporary r&b": "R&B",
    "r&b / hip-hop": "R&B",
    # Asian & Japanese subgenres
    "j-pop": "J-Pop",
    "j-rock": "J-Rock",
    "música asiática": "Música Asiática",
    "musica asiatica": "Música Asiática",
    "shibuya-kei / electronic": "Shibuya-kei",
    "shibuya-kei": "Shibuya-kei",
    "doujin": "Doujin",
    "anime": "Anime",
    # Rock, Metal & Alternative
    "alternative": "Alternativo",
    "alternativo": "Alternativo",
    "rock y alternativo": "Rock Alternativo",
    "rock alternativo": "Rock Alternativo",
    "alternative rock": "Rock Alternativo",
    "rock": "Rock",
    "metal": "Metal",
    "heavy metal": "Metal",
    "punk": "Punk",
    "indie rock": "Indie",
    "indie": "Indie",
    "country": "Country",
    # Soundtrack & Game
    "game": "Soundtrack",
    "game soundtrack": "Soundtrack",
    "game soundtrack / electronic": "Soundtrack",
    "soundtrack": "Soundtrack",
    "electronic / soundtrack": "Soundtrack",
    "music game song": "Soundtrack",
    "películas/juegos": "Soundtrack",
    "peliculas/juegos": "Soundtrack",
    "banda sonora": "Soundtrack",
    "ost": "Soundtrack",
    # Other
    "jazz": "Jazz",
    "blues": "Blues",
    "classical": "Clásica",
    "clásica": "Clásica",
    "clasica": "Clásica",
    "instrumental": "Instrumental",
    "ambient": "Ambient",
    "folk": "Folk",
}

# Heuristics for untagged underground / doujin / edit tracks not indexed in iTunes/Deezer
FALLBACK_ARTIST_GENRES: dict[str, str] = {
    "laur": "J-Core",
    "team grimoire": "J-Core",
    "roughsketch": "Hardcore Techno",
    "notebook records": "Hardcore Techno",
    "かめりあ": "J-Core",
    "camellia": "J-Core",
    "tanger": "Speedcore",
    "tn-shi": "Chiptune",
    "freetempo": "Shibuya-kei",
    "bardero$": "Hip-Hop",
    "barderos": "Hip-Hop",
    "akriila": "Pop Alternativo",
    "zell": "Trap",
    "s4nx": "Trap",
    "mikeanyway": "Trap",
    "minecraft": "Soundtrack",
    "c.r.o": "Urbano Latino",
    "cro": "Urbano Latino",
    "duki": "Trap Latino",
    "ysy a": "Trap Latino",
}


def _strip_accents(text: str) -> str:
    """Removes diacritics / accent marks for normalized key comparison."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if unicodedata.category(c) != "Mn")


def normalize_genre(genre_raw: str | None) -> str | None:
    """
    Normalizes a genre string against GENRE_MAPPING.
    Handles extra whitespace, case-insensitivity, accent-insensitivity, and slash separators.
    """
    if not genre_raw:
        return None

    cleaned = genre_raw.strip()
    if not cleaned or cleaned.lower() in (
        "unknown",
        "unknown genre",
        "sin género",
        "<sin género>",
        "none",
        "-",
    ):
        return None

    lowered = cleaned.lower()

    # 1. Direct lowercase lookup
    if lowered in GENRE_MAPPING:
        return GENRE_MAPPING[lowered]

    # 2. Accent-insensitive lookup (e.g. 'música tropical' vs 'musica tropical')
    lowered_no_accents = _strip_accents(lowered)
    for k, canonical in GENRE_MAPPING.items():
        if _strip_accents(k) == lowered_no_accents:
            return canonical

    # 3. Check slash/semicolon multi-genre separation (e.g. 'Trap; Hip-Hop' or 'Trap / Rap')
    if "/" in cleaned or ";" in cleaned:
        parts = [p.strip() for p in re.split(r"[\/;]", cleaned) if p.strip()]
        for part in parts:
            part_low = part.lower()
            if part_low in GENRE_MAPPING:
                return GENRE_MAPPING[part_low]
            part_no_acc = _strip_accents(part_low)
            for k, canonical in GENRE_MAPPING.items():
                if _strip_accents(k) == part_no_acc:
                    return canonical

    # If no mapping matched, return title-cased or trimmed original string
    return cleaned.capitalize() if cleaned.islower() else cleaned


def infer_genre_from_artist(artist: str | None) -> str | None:
    """
    Infers genre based on known underground / indie artists.
    """
    if not artist:
        return None

    artist_clean = artist.strip().lower()
    for known_artist, canonical_genre in FALLBACK_ARTIST_GENRES.items():
        if known_artist in artist_clean:
            return canonical_genre

    return None


def clean_genre(raw_genre: str | None, artist: str | None = None) -> str | None:
    """
    Canonical helper: Normalizes raw genre if provided, or infers from artist if missing.
    """
    normalized = normalize_genre(raw_genre)
    if normalized:
        return normalized

    if artist:
        return infer_genre_from_artist(artist)

    return None
