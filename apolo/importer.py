import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Tuple
import requests

from apolo.config import ApoloConfig, load_config
from apolo.downloader import DownloadedTrackInfo
from apolo.metadata.models import TrackMetadata
from apolo.pipeline import ProcessingPipeline
from apolo.playlists import PlaylistManager
from apolo.utils import sanitize_filename


@dataclass
class ImportedTrack:
    title: str
    artist: str
    album: Optional[str] = None
    album_artist: Optional[str] = None
    track_number: Optional[int] = None
    track_total: Optional[int] = None
    release_date: Optional[str] = None
    duration: Optional[float] = None
    cover_art_url: Optional[str] = None
    isrc: Optional[str] = None
    provider: str = "streaming"


@dataclass
class ImportedCollection:
    title: str
    creator: str
    tracks: List[ImportedTrack] = field(default_factory=list)
    cover_url: Optional[str] = None
    collection_type: str = "playlist"  # "playlist", "album", or "track"
    provider: str = "streaming"


class DeezerParser:
    @staticmethod
    def parse(url: str) -> Optional[ImportedCollection]:
        # Match playlist, album, or track
        match = re.search(r"deezer\.com/(?:[a-z]{2}/)?(playlist|album|track)/(\d+)", url)
        if not match:
            return None

        content_type = match.group(1)
        item_id = match.group(2)
        api_url = f"https://api.deezer.com/{content_type}/{item_id}"

        try:
            resp = requests.get(api_url, timeout=12)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if "error" in data:
                return None
        except Exception:
            return None

        if content_type == "playlist":
            tracks = []
            raw_tracks = data.get("tracks", {}).get("data", [])
            for idx, t in enumerate(raw_tracks, 1):
                tracks.append(
                    ImportedTrack(
                        title=t.get("title", ""),
                        artist=t.get("artist", {}).get("name", "Unknown Artist"),
                        album=t.get("album", {}).get("title"),
                        album_artist=t.get("artist", {}).get("name"),
                        track_number=idx,
                        track_total=len(raw_tracks),
                        duration=float(t.get("duration", 0)),
                        cover_art_url=t.get("album", {}).get("cover_xl") or t.get("album", {}).get("cover_big"),
                        isrc=t.get("isrc"),
                        provider="deezer",
                    )
                )
            return ImportedCollection(
                title=data.get("title", "Deezer Playlist"),
                creator=data.get("creator", {}).get("name", "Deezer"),
                tracks=tracks,
                cover_url=data.get("picture_xl") or data.get("picture_big"),
                collection_type="playlist",
                provider="deezer",
            )

        elif content_type == "album":
            tracks = []
            raw_tracks = data.get("tracks", {}).get("data", [])
            album_artist = data.get("artist", {}).get("name", "Unknown Artist")
            album_title = data.get("title", "Unknown Album")
            cover_url = data.get("cover_xl") or data.get("cover_big")
            release_date = data.get("release_date")
            total_tracks = data.get("nb_tracks") or len(raw_tracks)

            for idx, t in enumerate(raw_tracks, 1):
                tracks.append(
                    ImportedTrack(
                        title=t.get("title", ""),
                        artist=t.get("artist", {}).get("name", album_artist),
                        album=album_title,
                        album_artist=album_artist,
                        track_number=t.get("track_position") or idx,
                        track_total=total_tracks,
                        release_date=release_date,
                        duration=float(t.get("duration", 0)),
                        cover_art_url=cover_url,
                        isrc=t.get("isrc"),
                        provider="deezer",
                    )
                )
            return ImportedCollection(
                title=album_title,
                creator=album_artist,
                tracks=tracks,
                cover_url=cover_url,
                collection_type="album",
                provider="deezer",
            )

        elif content_type == "track":
            album = data.get("album", {})
            artist = data.get("artist", {})
            track = ImportedTrack(
                title=data.get("title", ""),
                artist=artist.get("name", "Unknown Artist"),
                album=album.get("title"),
                album_artist=artist.get("name"),
                track_number=data.get("track_position") or 1,
                release_date=data.get("release_date"),
                duration=float(data.get("duration", 0)),
                cover_art_url=album.get("cover_xl") or album.get("cover_big"),
                isrc=data.get("isrc"),
                provider="deezer",
            )
            return ImportedCollection(
                title=data.get("title", "Deezer Track"),
                creator=artist.get("name", "Unknown Artist"),
                tracks=[track],
                cover_url=album.get("cover_xl"),
                collection_type="track",
                provider="deezer",
            )

        return None


class SpotifyParser:
    @staticmethod
    def parse(url: str) -> Optional[ImportedCollection]:
        match = re.search(r"open\.spotify\.com/(?:intl-[a-z]+/)?(playlist|album|track)/([a-zA-Z0-9]+)", url)
        if not match:
            return None

        content_type = match.group(1)
        item_id = match.group(2)
        embed_url = f"https://open.spotify.com/embed/{content_type}/{item_id}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        try:
            resp = requests.get(embed_url, headers=headers, timeout=12)
            if resp.status_code != 200:
                return None
            html = resp.text
        except Exception:
            return None

        # Extract structured state JSON from Next.js payload or __NEXT_DATA__
        json_match = re.search(r'<script\s+id="__NEXT_DATA__"\s+type="application/json">([^<]+)</script>', html)
        if not json_match:
            # Fallback: search for initial state script
            json_match = re.search(r'<script\s+id="initial-state"\s+type="text/plain">([^<]+)</script>', html)

        if not json_match:
            # Try oEmbed for single metadata
            oembed_url = f"https://open.spotify.com/oembed?url={url}"
            try:
                oe_resp = requests.get(oembed_url, timeout=10)
                if oe_resp.status_code == 200:
                    oe_data = oe_resp.json()
                    title = oe_data.get("title", "Spotify Track")
                    return ImportedCollection(
                        title=title,
                        creator="Spotify",
                        tracks=[ImportedTrack(title=title, artist="Unknown Artist", provider="spotify")],
                        cover_url=oe_data.get("thumbnail_url"),
                        collection_type=content_type,
                        provider="spotify",
                    )
            except Exception:
                pass
            return None

        try:
            raw_data = json.loads(json_match.group(1))
        except Exception:
            return None

        entity = (
            raw_data.get("props", {})
            .get("pageProps", {})
            .get("state", {})
            .get("data", {})
            .get("entity", {})
        )

        if not entity:
            return None

        collection_name = entity.get("name") or entity.get("title", "Spotify Collection")
        collection_cover = None
        if entity.get("coverArt", {}).get("sources"):
            collection_cover = entity["coverArt"]["sources"][-1].get("url")

        track_list = entity.get("trackList") or []
        tracks: List[ImportedTrack] = []

        for idx, t in enumerate(track_list, 1):
            t_title = t.get("title") or t.get("name", "")
            t_artist = t.get("subtitle") or t.get("artists", [{}])[0].get("name", "Unknown Artist")
            dur_ms = t.get("duration", 0)
            dur_sec = float(dur_ms) / 1000.0 if dur_ms else None

            tracks.append(
                ImportedTrack(
                    title=t_title,
                    artist=t_artist,
                    album=collection_name if content_type == "album" else None,
                    album_artist=t_artist,
                    track_number=idx,
                    track_total=len(track_list),
                    duration=dur_sec,
                    cover_art_url=collection_cover,
                    isrc=t.get("isrc"),
                    provider="spotify",
                )
            )

        return ImportedCollection(
            title=collection_name,
            creator="Spotify",
            tracks=tracks,
            cover_url=collection_cover,
            collection_type=content_type,
            provider="spotify",
        )


class AppleMusicParser:
    @staticmethod
    def parse(url: str) -> Optional[ImportedCollection]:
        # Match Apple Music album or playlist ID
        match = re.search(r"music\.apple\.com/(?:[a-z]{2}/)?(?:album|playlist)/[^/]+/(\d+|pl\.[a-zA-Z0-9]+)", url)
        if not match:
            # Check for ?i=track_id
            match = re.search(r"[?&]i=(\d+)", url)
        if not match:
            return None

        item_id = match.group(1)
        api_url = f"https://itunes.apple.com/lookup?id={item_id}&entity=song"

        try:
            resp = requests.get(api_url, timeout=12)
            if resp.status_code != 200:
                return None
            data = resp.json()
            results = data.get("results", [])
            if not results:
                return None
        except Exception:
            return None

        collection_header = results[0]
        collection_title = collection_header.get("collectionName") or collection_header.get("trackName", "Apple Music")
        creator = collection_header.get("artistName", "Apple Music")
        cover_url = collection_header.get("artworkUrl100", "").replace("100x100bb", "1400x1400bb")

        tracks: List[ImportedTrack] = []
        song_results = [r for r in results if r.get("wrapperType") == "track"]
        if not song_results and collection_header.get("wrapperType") == "track":
            song_results = [collection_header]

        for r in song_results:
            dur_ms = r.get("trackTimeMillis", 0)
            dur_sec = float(dur_ms) / 1000.0 if dur_ms else None
            tracks.append(
                ImportedTrack(
                    title=r.get("trackName", ""),
                    artist=r.get("artistName", creator),
                    album=r.get("collectionName"),
                    album_artist=r.get("artistName", creator),
                    track_number=r.get("trackNumber"),
                    track_total=r.get("trackCount"),
                    release_date=r.get("releaseDate", "")[:10] if r.get("releaseDate") else None,
                    duration=dur_sec,
                    cover_art_url=r.get("artworkUrl100", "").replace("100x100bb", "1400x1400bb"),
                    provider="apple_music",
                )
            )

        return ImportedCollection(
            title=collection_title,
            creator=creator,
            tracks=tracks,
            cover_url=cover_url,
            collection_type="album" if len(tracks) > 1 else "track",
            provider="apple_music",
        )


class StreamingImporter:
    def __init__(self, config: Optional[ApoloConfig] = None):
        self.config = config or load_config()
        self.pipeline = ProcessingPipeline(self.config)
        self.playlist_mgr = PlaylistManager(self.config)

    def fetch_collection(self, url: str) -> Optional[ImportedCollection]:
        """Identifies provider and extracts tracklist and metadata from URL."""
        norm_url = url.lower()
        if "deezer.com" in norm_url:
            return DeezerParser.parse(url)
        elif "spotify.com" in norm_url:
            return SpotifyParser.parse(url)
        elif "music.apple.com" in norm_url or "itunes.apple.com" in norm_url:
            return AppleMusicParser.parse(url)
        return None

    def import_collection(
        self,
        url: str,
        create_m3u8: bool = True,
        dry_run: bool = False,
        on_progress: Optional[Callable[[str, str], None]] = None,
    ) -> Tuple[Optional[ImportedCollection], List[Tuple[Path, Optional[Path], TrackMetadata]], Optional[Path]]:
        """
        Parses collection URL, resolves high quality audio from YouTube/SoundCloud,
        tags with pristine original metadata, and optionally creates an M3U8 playlist.
        Returns: (collection, processed_results, playlist_path)
        """
        collection = self.fetch_collection(url)
        if not collection:
            return None, [], None

        if not collection.tracks:
            return collection, [], None

        results = []
        downloaded_paths: List[Path] = []

        total_tracks = len(collection.tracks)

        for idx, track in enumerate(collection.tracks, 1):
            search_query = f"{track.artist} - {track.title}"
            if on_progress:
                on_progress("searching", f"[{idx}/{total_tracks}] Locating audio for '{search_query}' ({collection.provider})...")

            # Search with ytsearch on YouTube Music / SoundCloud
            yt_query = f"ytsearch1:{search_query} audio"
            try:
                processed_items = self.pipeline.process_url(
                    yt_query,
                    origin=collection.provider,
                    dry_run=dry_run,
                    on_progress=on_progress,
                )

                if processed_items:
                    for dest_audio, dest_lrc, meta in processed_items:
                        # Override/Enrich with pristine official streaming metadata
                        if track.title:
                            meta.title = track.title
                        if track.artist:
                            meta.artist = track.artist
                        if track.album:
                            meta.album = track.album
                        if track.album_artist:
                            meta.album_artist = track.album_artist
                        if track.track_number:
                            meta.track_number = track.track_number
                        if track.track_total:
                            meta.track_total = track.track_total
                        if track.release_date:
                            meta.date = track.release_date
                        meta.origin = collection.provider

                        # In dry-run, recalculate expected path with accurate official tags
                        if dry_run:
                            dest_audio = self.pipeline.organizer.get_destination_path(meta)
                            dest_lrc = dest_audio.with_suffix(".lrc") if (self.config.organization.save_lrc_file and meta.synced_lyrics) else None

                        results.append((dest_audio, dest_lrc, meta))
                        downloaded_paths.append(dest_audio)
            except Exception:
                pass

        playlist_path = None
        if create_m3u8 and downloaded_paths and not dry_run:
            clean_name = sanitize_filename(f"{collection.creator} - {collection.title}" if collection.collection_type == "album" else collection.title)
            playlist_path, _ = self.playlist_mgr.create_manual_playlist(clean_name, downloaded_paths)

        return collection, results, playlist_path
