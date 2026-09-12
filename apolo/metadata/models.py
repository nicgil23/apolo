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

    def get_album_artist_or_artist(self) -> str:
        return self.album_artist or self.artist or "Unknown Artist"

    def get_year(self) -> str:
        if not self.date:
            return "Unknown Year"
        return self.date.split("-")[0].strip()

    def to_library_dict(self) -> dict:
        return {
            "title": self.title,
            "artist": self.artist,
            "album_artist": self.album_artist or self.artist,
            "album": self.album or "Unknown Album",
            "track_number": self.track_number,
            "track_total": self.track_total,
            "date": self.date,
            "genre": self.genre,
            "disc_number": self.disc_number,
            "disc_total": self.disc_total,
            "compilation": self.compilation,
            "cover_art": bool(self.cover_art_data or self.cover_art_url),
        }
