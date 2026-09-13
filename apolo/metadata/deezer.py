from typing import List, Optional
import requests

from apolo.metadata.models import TrackMetadata


class DeezerProvider:
    SEARCH_URL = "https://api.deezer.com/search"
    TRACK_URL = "https://api.deezer.com/track"
    ALBUM_URL = "https://api.deezer.com/album"

    def __init__(self, timeout: int = 10):
        self.timeout = timeout

    def search(self, query: str, limit: int = 5) -> List[TrackMetadata]:
        try:
            params = {"q": query, "limit": limit}
            resp = requests.get(self.SEARCH_URL, params=params, timeout=self.timeout)
            if resp.status_code != 200:
                return []

            data = resp.json()
            results: List[TrackMetadata] = []

            for item in data.get("data", []):
                title = item.get("title_short") or item.get("title")
                artist_obj = item.get("artist", {})
                artist = artist_obj.get("name")
                if not title or not artist:
                    continue

                track_id = item.get("id")
                album_obj = item.get("album", {})
                album_title = album_obj.get("title")
                album_id = album_obj.get("id")

                cover_url = album_obj.get("cover_xl") or album_obj.get("cover_big") or album_obj.get("cover_medium")
                duration = float(item.get("duration", 0)) or None

                release_date = None
                genre = None
                track_total = None
                track_position = item.get("track_position")
                disk_number = item.get("disk_number")

                # Fetch extra track & album details
                if track_id:
                    try:
                        trk_resp = requests.get(f"{self.TRACK_URL}/{track_id}", timeout=self.timeout)
                        if trk_resp.status_code == 200:
                            trk_data = trk_resp.json()
                            track_position = trk_data.get("track_position") or track_position
                            disk_number = trk_data.get("disk_number") or disk_number
                            release_date = trk_data.get("release_date")
                    except Exception:
                        pass

                if album_id and not release_date:
                    try:
                        alb_resp = requests.get(f"{self.ALBUM_URL}/{album_id}", timeout=self.timeout)
                        if alb_resp.status_code == 200:
                            alb_data = alb_resp.json()
                            release_date = alb_data.get("release_date") or release_date
                            track_total = alb_data.get("nb_tracks")
                            genres_data = alb_data.get("genres", {}).get("data", [])
                            if genres_data:
                                genre = genres_data[0].get("name")
                    except Exception:
                        pass

                track_meta = TrackMetadata(
                    title=title,
                    artist=artist,
                    album_artist=artist,
                    album=album_title,
                    track_number=track_position,
                    track_total=track_total,
                    date=release_date,
                    genre=genre,
                    disc_number=disk_number,
                    disc_total=1 if disk_number else None,
                    compilation=False,
                    cover_art_url=cover_url,
                    duration=duration,
                    provider_source="deezer",
                    source_id=str(track_id or ""),
                )
                results.append(track_meta)

            return results
        except Exception:
            return []
