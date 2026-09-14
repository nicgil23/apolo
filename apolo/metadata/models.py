from dataclasses import dataclass, field
from typing import Optional

METADATOS_BIBLIOTECA = [
    "title",
    "artist",
    "album_artist",
    "album",
    "track_number",
    "track_total",
    "date",
    "genre",
    "disc_number",
    "disc_total",
    "compilation",
    "cover_art",
    "origin",
]


@dataclass
class TrackMetadata:
    title: str
    artist: str
    album_artist: Optional[str] = None
    album: Optional[str] = None
    track_number: Optional[int] = None
    track_total: Optional[int] = None
    date: Optional[str] = None  # e.g., "2023" or "2023-05-18"
    genre: Optional[str] = None
    disc_number: Optional[int] = None
    disc_total: Optional[int] = None
    compilation: Optional[bool] = False
    cover_art_url: Optional[str] = None
    cover_art_data: Optional[bytes] = None
    synced_lyrics: Optional[str] = None
    duration: Optional[float] = None
    provider_source: Optional[str] = None
    source_id: Optional[str] = None
    origin: Optional[str] = None
    artists: list[str] = field(default_factory=list)
    main_artists: list[str] = field(default_factory=list)
    featured_artists: list[str] = field(default_factory=list)
    album_artists: list[str] = field(default_factory=list)

    extra_tags: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self):
        from apolo.utils import parse_artists
        if not self.artists and not self.main_artists:
            if self.artist:
                m, f, a, _ = parse_artists(self.artist, self.title)
                self.main_artists = m
                self.featured_artists = f
                self.artists = a
        elif self.main_artists and not self.artists:
            self.artists = list(self.main_artists) + [f for f in self.featured_artists if f not in self.main_artists]

        if not self.album_artists and self.album_artist:
            self.album_artists = [self.album_artist]
        elif self.album_artists and not self.album_artist:
            self.album_artist = self.album_artists[0]

    def get_album_artist_or_artist(self) -> str:
        if self.album_artist:
            return self.album_artist
        if self.main_artists:
            return self.main_artists[0]
        return self.artist or "Unknown Artist"

    def get_year(self) -> str:
        if not self.date:
            return "Unknown Year"
        import re
        match = re.search(r"\b(19\d{2}|20\d{2})\b", str(self.date))
        if match:
            return match.group(1)
        return str(self.date).split("-")[0].strip() or "Unknown Year"

    def to_library_dict(self) -> dict:
        return {
            "title": self.title,
            "artist": self.artist,
            "artists": self.artists,
            "main_artists": self.main_artists,
            "featured_artists": self.featured_artists,
            "album_artist": self.album_artist or (self.main_artists[0] if self.main_artists else self.artist),
            "album_artists": self.album_artists,
            "album": self.album or "Unknown Album",
            "track_number": self.track_number,
            "track_total": self.track_total,
            "date": self.date,
            "genre": self.genre,
            "disc_number": self.disc_number,
            "disc_total": self.disc_total,
            "compilation": self.compilation,
            "cover_art": bool(self.cover_art_data or self.cover_art_url),
            "origin": self.origin,
            "extra_tags": self.extra_tags,
        }

