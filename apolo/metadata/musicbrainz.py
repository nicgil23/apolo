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
                if not title or not artist_credit:
                    continue

                main_artists: List[str] = []
                featured_artists: List[str] = []
                all_artists: List[str] = []
                artist_parts: List[str] = []
                in_featured = False

                for credit in artist_credit:
                    if isinstance(credit, dict):
                        art_name = credit.get("artist", {}).get("name")
                        join = credit.get("joinphrase", "")
                    elif isinstance(credit, str):
                        art_name = credit
                        join = ""
                    else:
                        continue

                    if not art_name:
                        continue

                    if in_featured:
                        featured_artists.append(art_name)
                    else:
                        main_artists.append(art_name)

                    if art_name not in all_artists:
                        all_artists.append(art_name)
                    artist_parts.append(art_name)
                    if join:
                        artist_parts.append(join)
                        if any(w in join.lower() for w in ["feat", "ft.", "featuring", "with", "pres."]):
                            in_featured = True

                artist_display = "".join(artist_parts).strip() if artist_parts else (main_artists[0] if main_artists else None)
                if not artist_display:
                    continue

                duration_ms = rec.get("length")
                duration = float(duration_ms) / 1000.0 if duration_ms else None

                # Release info
                releases = rec.get("release-list", [])
                album = None
                album_artist = main_artists[0] if main_artists else artist_display
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

                    rel_artist_credit = rel.get("artist-credit", [])
                    if rel_artist_credit and isinstance(rel_artist_credit[0], dict):
                        album_artist = rel_artist_credit[0].get("artist", {}).get("name") or album_artist

                    medium_list = rel.get("medium-list", [])
                    disc_num = None
                    if medium_list:
                        for med in medium_list:
                            pos = med.get("position")
                            med_track_list = med.get("track-list", [])
                            if med_track_list:
                                track_num = int(med_track_list[0].get("number", 1))
                                track_total = med.get("track-count")
                                try:
                                    disc_num = int(pos) if pos else 1
                                except Exception:
                                    disc_num = 1
                                break
                        if disc_num is None:
                            try:
                                disc_num = int(medium_list[0].get("position", 1))
                            except Exception:
                                disc_num = 1

                    if release_id:
                        cover_url = f"https://coverartarchive.org/release/{release_id}/front-1200"

                tags = rec.get("tag-list", [])
                genre = tags[0].get("name") if tags else None

                track_meta = TrackMetadata(
                    title=title,
                    artist=artist_display,
                    artists=all_artists,
                    main_artists=main_artists,
                    featured_artists=featured_artists,
                    album_artist=album_artist,
                    album_artists=[album_artist] if album_artist else [],
                    album=album,
                    track_number=track_num,
                    track_total=int(track_total) if track_total else None,
                    date=date,
                    genre=genre,
                    disc_number=disc_num if track_num else None,
                    disc_total=len(medium_list) if medium_list and len(medium_list) > 1 else None,
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
