from typing import List, Optional
import musicbrainzngs

from apolo.metadata.models import TrackMetadata


class MusicBrainzProvider:
    def __init__(self, user_agent: str = "Apolo", version: str = "0.1.0", contact: str = "https://github.com/apolo"):
        musicbrainzngs.set_useragent(user_agent, version, contact)

    def search(self, query: str, limit: int = 5) -> List[TrackMetadata]:
        try:
            result = musicbrainzngs.search_recordings(query=query, limit=limit)
            recordings = result.get("recording-list", [])
            results: List[TrackMetadata] = []

            for rec in recordings:
                title = rec.get("title")
                artist_credit = rec.get("artist-credit", [])
                artist = artist_credit[0].get("artist", {}).get("name") if artist_credit else None
                if not title or not artist:
                    continue

                duration_ms = rec.get("length")
                duration = float(duration_ms) / 1000.0 if duration_ms else None

                # Release info
                releases = rec.get("release-list", [])
                album = None
                date = None
                track_num = None
                track_total = None
                release_id = None
                cover_url = None

                if releases:
                    rel = releases[0]
                    album = rel.get("title")
                    date = rel.get("date")
                    release_id = rel.get("id")

                    medium_list = rel.get("medium-list", [])
                    if medium_list:
                        track_total = medium_list[0].get("track-count")
                        track_list = medium_list[0].get("track-list", [])
                        if track_list:
                            track_num = int(track_list[0].get("number", 1))

                    if release_id:
                        cover_url = f"https://coverartarchive.org/release/{release_id}/front-1200"

                tags = rec.get("tag-list", [])
                genre = tags[0].get("name") if tags else None

                track_meta = TrackMetadata(
                    title=title,
                    artist=artist,
                    album_artist=artist,
                    album=album,
                    track_number=track_num,
                    track_total=int(track_total) if track_total else None,
                    date=date,
                    genre=genre,
                    disc_number=1 if track_num else None,
                    disc_total=1 if track_num else None,
                    compilation=False,
                    cover_art_url=cover_url,
                    duration=duration,
                    provider_source="musicbrainz",
                    source_id=rec.get("id"),
                )
                results.append(track_meta)

            return results
        except Exception:
            return []
