import re
from typing import List, Optional
import requests

from apolo.metadata.models import TrackMetadata


class iTunesProvider:
    SEARCH_URL = "https://itunes.apple.com/search"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def search(self, query: str, limit: int = 5) -> List[TrackMetadata]:
        try:
            params = {
                "term": query,
                "entity": "song",
                "limit": limit,
            }
            resp = requests.get(self.SEARCH_URL, params=params, timeout=self.timeout)
            if resp.status_code != 200:
                return []

            data = resp.json()
            results: List[TrackMetadata] = []

            for item in data.get("results", []):
                title = item.get("trackName")
                artist = item.get("artistName")
                if not title or not artist:
                    continue

                album = item.get("collectionName")
                track_num = item.get("trackNumber")
                track_count = item.get("trackCount")
                disc_num = item.get("discNumber")
                disc_count = item.get("discCount")
                genre = item.get("primaryGenreName")

                # Release date ISO: "2023-05-18T07:00:00Z" -> "2023-05-18"
                release_date_raw = item.get("releaseDate")
                date_str = None
                if release_date_raw:
                    date_str = release_date_raw.split("T")[0]

                # Cover art URL: upgrade 100x100 to high-res (e.g. 1400x1400)
                artwork_url = item.get("artworkUrl100")
                if artwork_url:
                    artwork_url = re.sub(r"\d+x\d+bb", "1400x1400bb", artwork_url)

                duration_ms = item.get("trackTimeMillis")
                duration = duration_ms / 1000.0 if duration_ms else None

                track_meta = TrackMetadata(
                    title=title,
                    artist=artist,
                    album_artist=artist,
                    album=album,
                    track_number=track_num,
                    track_total=track_count,
                    date=date_str,
                    genre=genre,
                    disc_number=disc_num,
                    disc_total=disc_count,
                    compilation=False,
                    cover_art_url=artwork_url,
                    duration=duration,
                    provider_source="itunes",
                    source_id=str(item.get("trackId", "")),
                )
                results.append(track_meta)

            return results
        except Exception:
            return []
