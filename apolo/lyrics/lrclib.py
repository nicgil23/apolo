from typing import Optional
import requests


class LRCLIBProvider:
    BASE_URL = "https://lrclib.net/api"

    def __init__(self, timeout: int = 10, synced_only: bool = True):
        self.timeout = timeout
        self.synced_only = synced_only

    def get_synced_lyrics(
        self,
        track_name: str,
        artist_name: str,
        album_name: Optional[str] = None,
        duration: Optional[float] = None,
    ) -> Optional[str]:
        # 1. Try exact get endpoint
        params = {
            "track_name": track_name,
            "artist_name": artist_name,
        }
        if album_name:
            params["album_name"] = album_name
        if duration:
            params["duration"] = str(int(duration))

        try:
            resp = requests.get(f"{self.BASE_URL}/get", params=params, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                synced = data.get("syncedLyrics")
                if synced and synced.strip():
                    return synced.strip()
        except Exception:
            pass

        # 2. Fallback to search endpoint
        try:
            search_params = {"q": f"{artist_name} {track_name}"}
            resp = requests.get(f"{self.BASE_URL}/search", params=search_params, timeout=self.timeout)
            if resp.status_code == 200:
                results = resp.json()
                for item in results:
                    synced = item.get("syncedLyrics")
                    if synced and synced.strip():
                        return synced.strip()
        except Exception:
            pass

        return None
