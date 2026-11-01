import re
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any

import mutagen
import requests

from apolo.audio.converter import AudioConverter
from apolo.audio.downloader import AudioDownloader
from apolo.config import ApoloConfig, load_config
from apolo.constants import AUDIO_EXTENSIONS
from apolo.library.organizer import LibraryOrganizer
from apolo.lyrics.lrclib import LRCLIBProvider
from apolo.metadata.matcher import MetadataMatcher
from apolo.metadata.models import TrackMetadata
from apolo.metadata.parsing import clean_track_title, extract_primary_artist
from apolo.storage.cleanup import StorageCleaner
from apolo.tagging.tagger import AudioTagger


def is_well_tagged(info: dict) -> bool:
    """
    Determines if a local track already has complete and reliable native metadata
    (e.g., downloaded from Soulseek or previously tagged) so that
    online provider rematching can be skipped to preserve original tags.
    """
    if not info.get("has_native_tags"):
        return False

    title = (info.get("title") or "").strip()
    artist = (info.get("artist") or "").strip()
    if not title or not artist:
        return False
    if artist.lower() in ["unknown", "unknown artist", "various artists"]:
        if not info.get("album") or info["album"].lower() in ["unknown", "unknown album"]:
            return False

    album = (info.get("album") or "").strip()
    has_extra_meta = any(
        [
            info.get("track_number") is not None,
            bool(info.get("date")),
            bool(info.get("genre")),
            bool(info.get("cover_art_data")),
            bool(info.get("album_artist")),
        ]
    )

    # If has title, artist, album and at least one extra metadata field
    if album and album.lower() not in ["unknown", "unknown album"] and has_extra_meta:
        return True

    # If it has title, artist and (track_number and date)
    if info.get("track_number") is not None and bool(info.get("date")):
        return True

    return False


class ProcessingPipeline:
    def __init__(self, config: ApoloConfig | None = None):
        self.config = config or load_config()
        self.downloader = AudioDownloader(self.config)
        self.matcher = MetadataMatcher(self.config)
        self.lyrics_provider = LRCLIBProvider(synced_only=self.config.providers.synced_lyrics_only)
        self.tagger = AudioTagger()
        self.organizer = LibraryOrganizer(self.config)
        self.converter = AudioConverter(self.config)

    def process_url(
        self,
        url: str,
        origin: str | None = None,
        suggested_title: str | None = None,
        dry_run: bool = False,
        candidate_selector: Callable[[list[tuple[float, TrackMetadata]], str], TrackMetadata | None]
        | None = None,
        on_progress: Callable[[str, str], None] | None = None,
        progress_callback: Callable[[float, str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
        on_playlist_init: Callable[[str, int, list[dict[str, Any]]], None] | None = None,
        on_subtrack_status: Callable[[str, str, str | None, int, float | None], None] | None = None,
        on_subtrack_progress: Callable[[str, float, str], None] | None = None,
        on_active_track: Callable[[int, int, str, str | None, float, str], None] | None = None,
        on_track_title: Callable[[str], None] | None = None,
    ) -> list[tuple[Path, Path | None, TrackMetadata]]:
        """
        Downloads URL, matches metadata, gets synced lyrics, tags, and organizes to library.
        Returns list of (dest_audio_path, dest_lrc_path, metadata)
        """
        if on_progress:
            on_progress("downloading", f"Downloading audio from {url}...")

        downloaded_items = self.downloader.download_url(
            url,
            origin=origin,
            suggested_title=suggested_title,
            progress_callback=progress_callback,
            cancel_check=cancel_check,
            on_playlist_init=on_playlist_init,
            on_subtrack_status=on_subtrack_status,
            on_subtrack_progress=on_subtrack_progress,
            on_active_track=on_active_track,
            on_track_title=on_track_title,
        )
        results = []

        for item in downloaded_items:
            opus_file = item.file_path
            search_query = f"{item.artist} {item.title}" if item.artist else item.title

            if on_progress:
                on_progress("matching", f"Searching metadata for '{search_query}'...")

            match = None
            if candidate_selector is not None:
                ranked = self.matcher.get_ranked_candidates(
                    query=search_query,
                    expected_title=item.title,
                    expected_artist=item.artist,
                    expected_album=item.album,
                    expected_duration=item.duration,
                )
                if ranked:
                    match = candidate_selector(ranked, search_query)
                    if (
                        match
                        and self.config.organization.embed_cover_art
                        and match.cover_art_url
                        and not match.cover_art_data
                    ):
                        match.cover_art_data = self.matcher._download_cover(match.cover_art_url)

            if not match and candidate_selector is None:
                match = self.matcher.find_best_match(
                    query=search_query,
                    expected_title=item.title,
                    expected_artist=item.artist,
                    expected_album=item.album,
                    expected_duration=item.duration,
                )

            if match:
                # Inherit playlist/source track info if missing from provider match
                if match.track_number is None and item.track_number is not None:
                    match.track_number = item.track_number
                if match.track_total is None and item.track_total is not None:
                    match.track_total = item.track_total
                if not match.album and item.album:
                    match.album = item.album
                if not match.album_artist and item.album_artist:
                    match.album_artist = item.album_artist
                if not match.date and item.release_date:
                    match.date = item.release_date
            else:
                # Use rich metadata from yt-dlp / YouTube Music
                cover_bytes = None
                if self.config.organization.embed_cover_art and item.thumbnail_url:
                    try:
                        resp = requests.get(item.thumbnail_url, timeout=10)
                        if resp.status_code == 200:
                            cover_bytes = resp.content
                    except Exception:
                        pass

                match = TrackMetadata(
                    title=item.title or "Unknown Title",
                    artist=item.artist or "Unknown Artist",
                    album_artist=item.album_artist or item.artist or "Unknown Artist",
                    album=item.album or "Single",
                    track_number=item.track_number,
                    track_total=item.track_total,
                    date=item.release_date,
                    cover_art_url=item.thumbnail_url,
                    cover_art_data=cover_bytes,
                    duration=item.duration,
                )

            # Set origin
            match.origin = item.origin or origin or self.config.downloader.default_origin

            if on_track_title and not item.subtrack_id:
                on_track_title(f"{match.artist} - {match.title}")

            if on_progress:
                on_progress(
                    "lyrics", f"Fetching synced lyrics for '{match.artist} - {match.title}'..."
                )

            synced_lyrics = self.lyrics_provider.get_synced_lyrics(
                track_name=match.title,
                artist_name=match.artist,
                album_name=match.album,
                duration=match.duration or item.duration,
            )
            match.synced_lyrics = synced_lyrics

            if dry_run:
                dest_audio = self.organizer.get_destination_path(match)
                dest_lrc = (
                    dest_audio.with_suffix(".lrc")
                    if (self.config.organization.save_lrc_file and match.synced_lyrics)
                    else None
                )
                # Clean up downloaded temp file in dry-run
                if opus_file.exists():
                    try:
                        opus_file.unlink()
                    except Exception:
                        pass
                results.append((dest_audio, dest_lrc, match))
                continue

            if on_progress:
                on_progress("tagging", f"Tagging {opus_file.name}...")

            self.tagger.tag_opus(opus_file, match)

            if on_progress:
                on_progress("organizing", f"Placing in library: {match.artist} - {match.title}...")

            dest_audio, dest_lrc = self.organizer.organize_track(opus_file, match)
            results.append((dest_audio, dest_lrc, match))

            if item.subtrack_id and on_subtrack_status:
                on_subtrack_status(item.subtrack_id, "completed", None, 0, None)

        return results

    def convert_to_opus(self, input_file: Path) -> Path:
        """
        Converts any audio/video file to .opus in temp_dir using ffmpeg at maximum perceptible quality.
        Uses libopus with VBR, compression level 10, and 48kHz audio resample.
        """
        return self.converter.convert_to_opus(input_file)

    def find_sidecar_lrc(self, file_path: Path) -> Path | None:
        """Finds companion .lrc file next to audio file."""
        return StorageCleaner.find_sidecar_lrc(file_path)

    def find_companion_cover(self, file_path: Path) -> Path | None:
        """Finds track-specific or album cover image in the same directory."""
        return StorageCleaner.find_companion_cover(file_path)

    def _cleanup_source_file_artifacts(self, file_path: Path) -> None:
        """Deletes track-specific sidecar files (.lrc, .jpg/.png) associated with file_path."""
        StorageCleaner.cleanup_source_file_artifacts(file_path)

    def cleanup_processed_directory(
        self, dir_path: Path, root_boundary: Path | None = None
    ) -> None:
        """
        Cleans up leftover images, lyrics, and junk files in dir_path if no audio files remain,
        and removes empty directories up to root_boundary.
        """
        protected = {self.config.directories.library_dir, self.config.directories.inbox_dir}
        StorageCleaner.cleanup_processed_directory(
            dir_path, root_boundary=root_boundary, protected_dirs=protected
        )

    def extract_file_info(self, file_path: Path) -> dict:
        """Extract existing title, artist, album, date, disc, track, origin, cover from file metadata or filename."""
        raw_title = None
        raw_artist = None
        raw_album_artist = None
        raw_album = None
        raw_track_num = None
        raw_track_total = None
        raw_disc_num = None
        raw_disc_total = None
        raw_compilation = False
        raw_controlled_anomaly = False
        raw_date = None
        raw_genre = None
        raw_origin = None
        raw_lyrics = None
        duration = None
        has_native_tags = False

        # Extract embedded cover art or companion cover image
        cover_art_data = AudioTagger.extract_cover_art_from_file(file_path)
        if not cover_art_data and self.config.organization.embed_cover_art:
            companion_cover = self.find_companion_cover(file_path)
            if companion_cover:
                try:
                    raw_img = companion_cover.read_bytes()
                    max_size = getattr(self.config.organization, "max_cover_size", 1400)
                    from apolo.tagging.cover import CoverManager

                    cover_art_data = CoverManager.optimize_image_bytes(raw_img, max_dim=max_size)
                except Exception:
                    pass

        # Check sidecar .lrc file first
        sidecar_lrc = self.find_sidecar_lrc(file_path)
        if sidecar_lrc:
            try:
                lrc_text = (
                    sidecar_lrc.read_text(encoding="utf-8", errors="ignore")
                    .strip()
                    .lstrip("\ufeff")
                )
                if lrc_text:
                    raw_lyrics = lrc_text
            except Exception:
                pass

        try:
            audio = mutagen.File(file_path)
            if audio is not None:
                duration = getattr(audio.info, "length", None)
                tags = getattr(audio, "tags", None)
                if tags:
                    has_native_tags = True

                    def safe_get_tag(keys):
                        for k in keys:
                            try:
                                if k in tags:
                                    val = tags[k]
                                    if isinstance(val, (list, tuple)) and len(val) > 0:
                                        return str(val[0])
                                    elif val is not None:
                                        return str(val)
                            except Exception:
                                continue
                        return None

                    raw_title = safe_get_tag(["TITLE", "title", "TIT2", "\xa9nam", "©nam"])
                    raw_artist = safe_get_tag(["ARTIST", "artist", "TPE1", "\xa9ART", "©ART"])
                    raw_album_artist = safe_get_tag(["ALBUMARTIST", "albumartist", "TPE2", "aART"])
                    raw_album = safe_get_tag(["ALBUM", "album", "TALB", "\xa9alb", "©alb"])
                    raw_date = safe_get_tag(["DATE", "date", "TDRC", "TYER", "\xa9day", "©day"])
                    raw_genre = safe_get_tag(["GENRE", "genre", "TCON", "\xa9gen", "©gen"])
                    raw_origin = safe_get_tag(
                        ["ORIGIN", "origin", "SOURCE", "source", "ORIGEN", "origen"]
                    )
                    tag_lyrics = safe_get_tag(
                        ["LYRICS", "lyrics", "USLT", "UNSYNCEDLYRICS", "\xa9lyr", "©lyr"]
                    )
                    if tag_lyrics:
                        raw_lyrics = tag_lyrics

                    track_str = safe_get_tag(["TRACKNUMBER", "tracknumber", "TRCK"])
                    if track_str:
                        try:
                            parts = track_str.split("/")
                            raw_track_num = int(parts[0])
                            if len(parts) > 1:
                                raw_track_total = int(parts[1])
                        except Exception:
                            pass
                    try:
                        if "trkn" in tags:
                            trkn = tags["trkn"][0]
                            if isinstance(trkn, (tuple, list)):
                                if trkn[0]:
                                    raw_track_num = int(trkn[0])
                                if len(trkn) > 1 and trkn[1]:
                                    raw_track_total = int(trkn[1])
                    except Exception:
                        pass
                    if raw_track_total is None:
                        total_str = safe_get_tag(
                            ["TRACKTOTAL", "tracktotal", "TOTALTRACKS", "totaltracks"]
                        )
                        if total_str:
                            try:
                                raw_track_total = int(total_str.split("/")[0])
                            except Exception:
                                pass

                    disc_str = safe_get_tag(["DISCNUMBER", "discnumber", "TPOS"])
                    if disc_str:
                        try:
                            parts = disc_str.split("/")
                            raw_disc_num = int(parts[0])
                            if len(parts) > 1:
                                raw_disc_total = int(parts[1])
                        except Exception:
                            pass
                    try:
                        if "disk" in tags:
                            disk = tags["disk"][0]
                            if isinstance(disk, (tuple, list)):
                                if disk[0]:
                                    raw_disc_num = int(disk[0])
                                if len(disk) > 1 and disk[1]:
                                    raw_disc_total = int(disk[1])
                    except Exception:
                        pass
                    if raw_disc_total is None:
                        dtotal_str = safe_get_tag(
                            ["DISCTOTAL", "disctotal", "TOTALDISCS", "totaldiscs"]
                        )
                        if dtotal_str:
                            try:
                                raw_disc_total = int(dtotal_str.split("/")[0])
                            except Exception:
                                pass

                    comp_str = safe_get_tag(["COMPILATION", "compilation", "TCMP"])
                    if comp_str:
                        raw_compilation = comp_str in ["1", "true", "True"]
                    try:
                        if "cpil" in tags:
                            raw_compilation = bool(tags["cpil"])
                    except Exception:
                        pass

                    raw_controlled_anomaly = False
                    anomaly_str = safe_get_tag(
                        [
                            "CONTROLLED_ANOMALY",
                            "controlled_anomaly",
                            "PARTIAL_ALBUM",
                            "partial_album",
                            "ANOMALIA_CONTROLADA",
                            "anomalia_controlada",
                        ]
                    )
                    if anomaly_str:
                        raw_controlled_anomaly = anomaly_str.strip().lower() in [
                            "1",
                            "true",
                            "yes",
                            "si",
                            "sí",
                        ]

        except Exception:
            pass

        extra_tags = {}
        if has_native_tags and audio and getattr(audio, "tags", None):
            standard_handled = {
                "TITLE",
                "TIT2",
                "ARTIST",
                "TPE1",
                "ALBUMARTIST",
                "TPE2",
                "ALBUM",
                "TALB",
                "DATE",
                "TDRC",
                "TYER",
                "GENRE",
                "TCON",
                "ORIGIN",
                "SOURCE",
                "ORIGEN",
                "LYRICS",
                "USLT",
                "UNSYNCEDLYRICS",
                "TRACKNUMBER",
                "TRCK",
                "TRACKTOTAL",
                "TOTALTRACKS",
                "DISCNUMBER",
                "TPOS",
                "DISCTOTAL",
                "TOTALDISCS",
                "COMPILATION",
                "TCMP",
                "METADATA_BLOCK_PICTURE",
                "APIC",
                "COVR",
            }
            try:
                for k in audio.tags.keys():
                    k_str = str(k).upper()
                    if k_str not in standard_handled and not k_str.startswith("---"):
                        val = audio.tags[k]
                        if isinstance(val, (list, tuple)):
                            extra_tags[k_str] = [str(x) for x in val]
                        else:
                            extra_tags[k_str] = [str(val)]
            except Exception:
                pass

        # Fallback to parse track number from filename if missing from tags
        if raw_track_num is None:
            match_num = re.match(r"^(\d{1,3})\s*[-_.]\s*", file_path.name)
            if match_num:
                try:
                    raw_track_num = int(match_num.group(1))
                except Exception:
                    pass

        if not raw_title:
            cleaned_title, parsed_artist = clean_track_title(file_path.stem)
            raw_title = cleaned_title
            if not raw_artist:
                raw_artist = parsed_artist

        if not raw_album_artist:
            raw_album_artist = extract_primary_artist(raw_artist)

        return {
            "title": raw_title,
            "artist": raw_artist,
            "album_artist": raw_album_artist,
            "album": raw_album,
            "track_number": raw_track_num,
            "track_total": raw_track_total,
            "disc_number": raw_disc_num,
            "disc_total": raw_disc_total,
            "compilation": raw_compilation,
            "date": raw_date,
            "genre": raw_genre,
            "origin": raw_origin,
            "lyrics": raw_lyrics,
            "duration": duration,
            "cover_art_data": cover_art_data,
            "has_native_tags": has_native_tags,
            "controlled_anomaly": raw_controlled_anomaly,
            "extra_tags": extra_tags,
        }

    def process_file(
        self,
        file_path: Path,
        origin: str | None = None,
        force_rematch: bool = False,
        dry_run: bool = False,
        preserve_lossless: bool | None = None,
        candidate_selector: Callable[[list[tuple[float, TrackMetadata]], str], TrackMetadata | None]
        | None = None,
        on_progress: Callable[[str, str], None] | None = None,
    ) -> tuple[Path, Path | None, TrackMetadata] | None:
        """Processes a single local audio or video file."""
        if not file_path.exists() or file_path.suffix.lower() not in AUDIO_EXTENSIONS:
            return None

        if on_progress:
            on_progress("converting", f"Processing {file_path.name}...")

        info = self.extract_file_info(file_path)
        raw_title = info["title"]
        raw_artist = info["artist"]
        duration = info["duration"]

        well_tagged = (
            is_well_tagged(info)
            and self.config.downloader.preserve_existing_tags
            and not force_rematch
        )

        if well_tagged:
            # Preserve existing metadata completely without online provider mutations
            match = TrackMetadata(
                title=raw_title or file_path.stem,
                artist=raw_artist or "Unknown Artist",
                album_artist=info["album_artist"] or raw_artist or "Unknown Artist",
                album=info["album"] or "Single",
                track_number=info["track_number"],
                track_total=info["track_total"],
                disc_number=info["disc_number"],
                disc_total=info["disc_total"],
                compilation=info["compilation"],
                date=info["date"],
                genre=info["genre"],
                cover_art_data=info["cover_art_data"],
                synced_lyrics=info["lyrics"],
                duration=duration,
                provider_source="existing_metadata",
                extra_tags=info.get("extra_tags", {}),
            )
        else:
            search_query = f"{raw_artist} {raw_title}" if raw_artist else raw_title
            if on_progress:
                on_progress("matching", f"Searching metadata for '{search_query}'...")

            match = None
            if candidate_selector is not None:
                ranked = self.matcher.get_ranked_candidates(
                    query=search_query,
                    expected_title=raw_title,
                    expected_artist=raw_artist,
                    expected_album=info["album"],
                    expected_duration=duration,
                )
                if ranked:
                    match = candidate_selector(ranked, search_query)
                    if (
                        match
                        and self.config.organization.embed_cover_art
                        and match.cover_art_url
                        and not match.cover_art_data
                    ):
                        match.cover_art_data = self.matcher._download_cover(match.cover_art_url)

            if not match and candidate_selector is None:
                match = self.matcher.find_best_match(
                    query=search_query,
                    expected_title=raw_title,
                    expected_artist=raw_artist,
                    expected_album=info["album"],
                    expected_duration=duration,
                )

            if not match:
                match = TrackMetadata(
                    title=raw_title or file_path.stem,
                    artist=raw_artist or "Unknown Artist",
                    album_artist=info["album_artist"] or raw_artist or "Unknown Artist",
                    album=info["album"] or "Single",
                    track_number=info["track_number"],
                    track_total=info["track_total"],
                    disc_number=info["disc_number"],
                    disc_total=info["disc_total"],
                    compilation=info["compilation"],
                    date=info["date"],
                    genre=info["genre"],
                    cover_art_data=info["cover_art_data"],
                    synced_lyrics=info["lyrics"],
                    duration=duration,
                    extra_tags=info.get("extra_tags", {}),
                )
            else:
                if match.track_number is None and info["track_number"] is not None:
                    match.track_number = info["track_number"]
                if match.track_total is None and info["track_total"] is not None:
                    match.track_total = info["track_total"]
                if not match.album and info["album"]:
                    match.album = info["album"]
                if not match.genre and info["genre"]:
                    match.genre = info["genre"]
                if not match.cover_art_data and info["cover_art_data"]:
                    match.cover_art_data = info["cover_art_data"]
                if not match.synced_lyrics and info["lyrics"]:
                    match.synced_lyrics = info["lyrics"]
                if info.get("extra_tags"):
                    match.extra_tags = dict(info["extra_tags"])

        # Assign origin: CLI param > existing tag in file > config default
        final_origin = origin or info.get("origin") or self.config.downloader.default_origin
        match.origin = final_origin

        # Fetch synced lyrics if missing
        if not match.synced_lyrics:
            if on_progress:
                on_progress(
                    "lyrics", f"Fetching synced lyrics for '{match.artist} - {match.title}'..."
                )

            synced_lyrics = self.lyrics_provider.get_synced_lyrics(
                track_name=match.title,
                artist_name=match.artist,
                album_name=match.album,
                duration=match.duration or duration,
            )
            match.synced_lyrics = synced_lyrics

        should_preserve_flac = file_path.suffix.lower() == ".flac" and (
            preserve_lossless
            if preserve_lossless is not None
            else getattr(self.config.downloader, "preserve_lossless", False)
        )
        ext = ".flac" if should_preserve_flac else ".opus"

        if dry_run:
            dest_audio = self.organizer.get_destination_path(match, extension=ext)
            dest_lrc = (
                dest_audio.with_suffix(".lrc")
                if (self.config.organization.save_lrc_file and match.synced_lyrics)
                else None
            )
            return dest_audio, dest_lrc, match

        if should_preserve_flac:
            if on_progress:
                on_progress("tagging", f"Tagging FLAC {file_path.name}...")
            self.tagger.tag_flac(file_path, match)
            if on_progress:
                on_progress(
                    "organizing", f"Placing in library: {match.artist} - {match.title} (FLAC)..."
                )
            dest_audio, dest_lrc = self.organizer.organize_track(
                file_path, match, extension=".flac"
            )
            self._cleanup_source_file_artifacts(file_path)
            self.cleanup_processed_directory(
                file_path.parent, root_boundary=self.config.directories.inbox_dir
            )
            return dest_audio, dest_lrc, match

        # Convert to high-quality .opus if not already .opus
        opus_file = self.convert_to_opus(file_path)

        if on_progress:
            on_progress("tagging", f"Tagging {opus_file.name}...")

        self.tagger.tag_opus(opus_file, match)

        if on_progress:
            on_progress("organizing", f"Placing in library: {match.artist} - {match.title}...")

        dest_audio, dest_lrc = self.organizer.organize_track(opus_file, match, extension=".opus")

        # If source was not the converted temp file, remove original file if it was converted
        if file_path != opus_file and file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass

        self._cleanup_source_file_artifacts(file_path)
        self.cleanup_processed_directory(
            file_path.parent, root_boundary=self.config.directories.inbox_dir
        )

        return dest_audio, dest_lrc, match

    def process_directory(
        self,
        directory: Path,
        origin: str | None = None,
        force_rematch: bool = False,
        dry_run: bool = False,
        preserve_lossless: bool | None = None,
        candidate_selector: Callable[[list[tuple[float, TrackMetadata]], str], TrackMetadata | None]
        | None = None,
        on_progress: Callable[[str, str], None] | None = None,
    ) -> list[tuple[Path, Path | None, TrackMetadata]]:
        """Recursively processes all audio files in a directory."""
        results = []
        if not directory.exists() or not directory.is_dir():
            return results

        files = [
            p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
        ]
        source_dirs = {p.parent for p in files}

        for file_path in sorted(files):
            res = self.process_file(
                file_path,
                origin=origin,
                force_rematch=force_rematch,
                dry_run=dry_run,
                preserve_lossless=preserve_lossless,
                candidate_selector=candidate_selector,
                on_progress=on_progress,
            )
            if res:
                results.append(res)

        # Check album consensus on processed results
        from apolo.utils import infer_consensus_album_artist, infer_consensus_date

        albums_grouped: dict[tuple[str, str], list[tuple[Path, Path | None, TrackMetadata]]] = {}
        for r in results:
            alb = r[2].album
            if alb and alb.lower() not in ["single", "singles", "unknown"]:
                prim_artist = extract_primary_artist(r[2].album_artist or r[2].artist) or ""
                albums_grouped.setdefault((alb.lower(), prim_artist.lower()), []).append(r)

        for (alb_name, alb_artist_key), track_tuples in albums_grouped.items():
            if len(track_tuples) >= 2:
                metas = [t[2] for t in track_tuples]
                consensus_artist = infer_consensus_album_artist(metas, threshold=0.50)
                consensus_date = infer_consensus_date(metas, threshold=0.50)
                changed_any = False
                for dest_audio, dest_lrc, meta in track_tuples:
                    tag_updates = {}
                    if consensus_artist and meta.album_artist != consensus_artist:
                        meta.album_artist = consensus_artist
                        meta.album_artists = [consensus_artist]
                        tag_updates["album_artist"] = consensus_artist
                        changed_any = True
                    if consensus_date and meta.date != consensus_date:
                        meta.date = consensus_date
                        tag_updates["date"] = consensus_date
                        changed_any = True

                    if tag_updates and not dry_run and dest_audio.exists():
                        AudioTagger.update_tags(dest_audio, tag_updates)

                if changed_any and not dry_run:
                    self.reorganize_paths([t[0] for t in track_tuples if t[0].exists()])

        if not dry_run:
            for d in sorted(source_dirs, key=lambda p: len(p.parts), reverse=True):
                self.cleanup_processed_directory(d, root_boundary=directory)

        return results

    def process_paths(
        self,
        paths: list[Path],
        origin: str | None = None,
        force_rematch: bool = False,
        dry_run: bool = False,
        preserve_lossless: bool | None = None,
        candidate_selector: Callable[[list[tuple[float, TrackMetadata]], str], TrackMetadata | None]
        | None = None,
        on_progress: Callable[[str, str], None] | None = None,
    ) -> list[tuple[Path, Path | None, TrackMetadata]]:
        """Recursively processes all files and directories in the provided list."""
        results = []
        for path in paths:
            if not path.exists():
                continue
            if path.is_dir():
                results.extend(
                    self.process_directory(
                        path,
                        origin=origin,
                        force_rematch=force_rematch,
                        dry_run=dry_run,
                        preserve_lossless=preserve_lossless,
                        candidate_selector=candidate_selector,
                        on_progress=on_progress,
                    )
                )
            elif path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS:
                res = self.process_file(
                    path,
                    origin=origin,
                    force_rematch=force_rematch,
                    dry_run=dry_run,
                    preserve_lossless=preserve_lossless,
                    candidate_selector=candidate_selector,
                    on_progress=on_progress,
                )
                if res:
                    results.append(res)
        return results

    def reorganize_paths(
        self,
        paths: list[Path] | None = None,
        dry_run: bool = False,
        on_progress: Callable[[str, str], None] | None = None,
    ) -> list[tuple[Path, Path]]:
        """
        Scans all files in given paths (or library_dir if None/empty), recalculates paths based on current rules,
        moves files/lyrics that are misplaced, and removes empty directories.
        Returns list of (old_path, new_path)
        """
        if not paths:
            target_dir = self.config.directories.library_dir
            if not target_dir.exists():
                return []
            candidate_files = [
                p
                for p in target_dir.rglob("*")
                if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
            ]
        else:
            candidate_files = []
            for p in paths:
                if not p.exists():
                    continue
                if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
                    candidate_files.append(p)
                elif p.is_dir():
                    candidate_files.extend(
                        [
                            f
                            for f in p.rglob("*")
                            if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
                        ]
                    )

        # Deduplicate and sort
        seen = set()
        files = []
        for f in candidate_files:
            resolved = f.resolve()
            if resolved not in seen:
                seen.add(resolved)
                files.append(f)
        files.sort()

        moved = []
        lib_dir_resolved = self.config.directories.library_dir.resolve()

        for file_path in files:
            info = self.extract_file_info(file_path)
            meta = TrackMetadata(
                title=info["title"] or file_path.stem,
                artist=info["artist"] or "Unknown Artist",
                album_artist=info["album_artist"] or info["artist"] or "Unknown Artist",
                album=info["album"] or "Single",
                track_number=info["track_number"],
                track_total=info["track_total"],
                disc_number=info["disc_number"],
                disc_total=info["disc_total"],
                compilation=info["compilation"],
                date=info["date"],
            )

            file_ext = file_path.suffix.lower()
            ext = file_ext if file_ext in [".flac", ".opus"] else ".opus"
            expected_dest = self.organizer.get_destination_path(meta, extension=ext)
            if file_path.resolve() != expected_dest.resolve():
                if on_progress:
                    on_progress(
                        "moving", f"Relocating: {file_path.name} -> {expected_dest.parent.name}"
                    )

                if not dry_run:
                    expected_dest.parent.mkdir(parents=True, exist_ok=True)

                    # Move companion .lrc if exists
                    old_lrc = file_path.with_suffix(".lrc")
                    new_lrc = expected_dest.with_suffix(".lrc")
                    if old_lrc.exists():
                        shutil.move(str(old_lrc), str(new_lrc))

                    shutil.move(str(file_path), str(expected_dest))

                    # Move companion cover images if old folder has no more audio files
                    old_parent = file_path.parent
                    if old_parent.exists() and old_parent != expected_dest.parent:
                        remaining_audio = [
                            p
                            for p in old_parent.iterdir()
                            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
                        ]
                        if not remaining_audio:
                            for img_name in [
                                "cover.jpg",
                                "cover.png",
                                "folder.jpg",
                                "folder.png",
                                "front.jpg",
                                "front.png",
                            ]:
                                old_img = old_parent / img_name
                                new_img = expected_dest.parent / img_name
                                if old_img.exists() and not new_img.exists():
                                    try:
                                        shutil.move(str(old_img), str(new_img))
                                    except Exception:
                                        pass

                    # Clean up empty parent directories
                    parent = file_path.parent
                    while parent.resolve() != lib_dir_resolved and parent.exists():
                        try:
                            if not any(parent.iterdir()):
                                parent.rmdir()
                                parent = parent.parent
                            else:
                                break
                        except Exception:
                            break

                moved.append((file_path, expected_dest))

        return moved

    def reorganize_library(
        self,
        library_dir: Path | None = None,
        dry_run: bool = False,
        on_progress: Callable[[str, str], None] | None = None,
    ) -> list[tuple[Path, Path]]:
        paths = [library_dir] if library_dir else None
        return self.reorganize_paths(paths, dry_run=dry_run, on_progress=on_progress)
