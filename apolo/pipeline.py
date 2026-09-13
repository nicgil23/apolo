import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable, List, Optional, Tuple
import mutagen
import requests

from apolo.config import ApoloConfig, load_config
from apolo.downloader import AudioDownloader, DownloadedTrackInfo
from apolo.lyrics.lrclib import LRCLIBProvider
from apolo.metadata.matcher import MetadataMatcher
from apolo.metadata.models import TrackMetadata
from apolo.organizer import LibraryOrganizer
from apolo.tagger import AudioTagger
from apolo.utils import clean_track_title, extract_primary_artist

AUDIO_EXTENSIONS = {".opus", ".mp3", ".flac", ".m4a", ".ogg", ".wav", ".aac"}


class ProcessingPipeline:
    def __init__(self, config: Optional[ApoloConfig] = None):
        self.config = config or load_config()
        self.downloader = AudioDownloader(self.config)
        self.matcher = MetadataMatcher(self.config)
        self.lyrics_provider = LRCLIBProvider(synced_only=self.config.providers.synced_lyrics_only)
        self.tagger = AudioTagger()
        self.organizer = LibraryOrganizer(self.config)

    def process_url(
        self,
        url: str,
        on_progress: Optional[Callable[[str, str], None]] = None,
    ) -> List[Tuple[Path, Optional[Path], TrackMetadata]]:
        """
        Downloads URL, matches metadata, gets synced lyrics, tags, and organizes to library.
        Returns list of (dest_audio_path, dest_lrc_path, metadata)
        """
        if on_progress:
            on_progress("downloading", f"Downloading audio from {url}...")

        downloaded_items = self.downloader.download_url(url)
        results = []

        for item in downloaded_items:
            opus_file = item.file_path
            search_query = f"{item.artist} {item.title}" if item.artist else item.title

            if on_progress:
                on_progress("matching", f"Searching metadata for '{search_query}'...")

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

            if on_progress:
                on_progress("lyrics", f"Fetching synced lyrics for '{match.artist} - {match.title}'...")

            synced_lyrics = self.lyrics_provider.get_synced_lyrics(
                track_name=match.title,
                artist_name=match.artist,
                album_name=match.album,
                duration=match.duration or item.duration,
            )
            match.synced_lyrics = synced_lyrics

            if on_progress:
                on_progress("tagging", f"Tagging {opus_file.name}...")

            self.tagger.tag_opus(opus_file, match)

            if on_progress:
                on_progress("organizing", f"Placing in library: {match.artist} - {match.title}...")

            dest_audio, dest_lrc = self.organizer.organize_track(opus_file, match)
            results.append((dest_audio, dest_lrc, match))

        return results

    def convert_to_opus(self, input_file: Path) -> Path:
        """Converts any audio file to .opus in temp_dir using ffmpeg at max quality."""
        if input_file.suffix.lower() == ".opus":
            return input_file

        output_file = self.config.directories.temp_dir / f"{input_file.stem}.opus"
        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_file),
            "-c:a",
            "libopus",
            "-b:a",
            "320k",
            "-vbr",
            "on",
            "-compression_level",
            "10",
            str(output_file),
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return output_file

    def extract_file_info(self, file_path: Path) -> dict:
        """Extract existing title, artist, album, date, disc, track from file metadata or filename."""
        raw_title = None
        raw_artist = None
        raw_album_artist = None
        raw_album = None
        raw_track_num = None
        raw_track_total = None
        raw_disc_num = None
        raw_disc_total = None
        raw_compilation = False
        raw_date = None
        duration = None

        try:
            audio = mutagen.File(file_path)
            if audio is not None:
                duration = getattr(audio.info, "length", None)
                tags = getattr(audio, "tags", None)
                if tags:
                    for k in ["TITLE", "title", "TIT2"]:
                        if k in tags:
                            raw_title = str(tags[k][0])
                            break
                    for k in ["ARTIST", "artist", "TPE1"]:
                        if k in tags:
                            raw_artist = str(tags[k][0])
                            break
                    for k in ["ALBUMARTIST", "albumartist", "TPE2"]:
                        if k in tags:
                            raw_album_artist = str(tags[k][0])
                            break
                    for k in ["ALBUM", "album", "TALB"]:
                        if k in tags:
                            raw_album = str(tags[k][0])
                            break
                    for k in ["DATE", "date", "TDRC", "TYER"]:
                        if k in tags:
                            raw_date = str(tags[k][0])
                            break
                    for k in ["TRACKNUMBER", "tracknumber", "TRCK"]:
                        if k in tags:
                            try:
                                parts = str(tags[k][0]).split("/")
                                raw_track_num = int(parts[0])
                                if len(parts) > 1:
                                    raw_track_total = int(parts[1])
                            except Exception:
                                pass
                            break
                    for k in ["DISCNUMBER", "discnumber", "TPOS"]:
                        if k in tags:
                            try:
                                parts = str(tags[k][0]).split("/")
                                raw_disc_num = int(parts[0])
                                if len(parts) > 1:
                                    raw_disc_total = int(parts[1])
                            except Exception:
                                pass
                            break
                    for k in ["COMPILATION", "compilation", "TCMP"]:
                        if k in tags:
                            raw_compilation = str(tags[k][0]) in ["1", "true", "True"]
                            break
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
            "duration": duration,
        }

    def process_file(
        self,
        file_path: Path,
        on_progress: Optional[Callable[[str, str], None]] = None,
    ) -> Optional[Tuple[Path, Optional[Path], TrackMetadata]]:
        """Processes a single local audio file."""
        if not file_path.exists() or file_path.suffix.lower() not in AUDIO_EXTENSIONS:
            return None

        if on_progress:
            on_progress("converting", f"Processing {file_path.name}...")

        info = self.extract_file_info(file_path)
        raw_title = info["title"]
        raw_artist = info["artist"]
        duration = info["duration"]
        search_query = f"{raw_artist} {raw_title}" if raw_artist else raw_title

        if on_progress:
            on_progress("matching", f"Searching metadata for '{search_query}'...")

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
                duration=duration,
            )
        else:
            if match.track_number is None and info["track_number"] is not None:
                match.track_number = info["track_number"]
            if match.track_total is None and info["track_total"] is not None:
                match.track_total = info["track_total"]
            if not match.album and info["album"]:
                match.album = info["album"]

        if on_progress:
            on_progress("lyrics", f"Fetching synced lyrics for '{match.artist} - {match.title}'...")

        synced_lyrics = self.lyrics_provider.get_synced_lyrics(
            track_name=match.title,
            artist_name=match.artist,
            album_name=match.album,
            duration=match.duration or duration,
        )
        match.synced_lyrics = synced_lyrics

        # Convert to opus if necessary
        opus_file = self.convert_to_opus(file_path)

        if on_progress:
            on_progress("tagging", f"Tagging {opus_file.name}...")

        self.tagger.tag_opus(opus_file, match)

        if on_progress:
            on_progress("organizing", f"Placing in library: {match.artist} - {match.title}...")

        dest_audio, dest_lrc = self.organizer.organize_track(opus_file, match)

        # If source was not the converted temp file, remove original file if it was converted
        if file_path != opus_file and file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass

        return dest_audio, dest_lrc, match

    def process_directory(
        self,
        directory: Path,
        on_progress: Optional[Callable[[str, str], None]] = None,
    ) -> List[Tuple[Path, Optional[Path], TrackMetadata]]:
        """Recursively processes all audio files in a directory."""
        results = []
        files = [p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS]

        for file_path in sorted(files):
            res = self.process_file(file_path, on_progress=on_progress)
            if res:
                results.append(res)

        return results

    def reorganize_library(
        self,
        library_dir: Optional[Path] = None,
        on_progress: Optional[Callable[[str, str], None]] = None,
    ) -> List[Tuple[Path, Path]]:
        """
        Scans all files in library_dir, recalculates paths based on current rules,
        moves files/lyrics that are misplaced, and removes empty directories.
        Returns list of (old_path, new_path)
        """
        target_dir = library_dir or self.config.directories.library_dir
        if not target_dir.exists():
            return []

        files = [p for p in target_dir.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS]
        moved = []

        for file_path in sorted(files):
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

            expected_dest = self.organizer.get_destination_path(meta)
            if file_path.resolve() != expected_dest.resolve():
                if on_progress:
                    on_progress("moving", f"Relocating: {file_path.name} -> {expected_dest.parent.name}")

                expected_dest.parent.mkdir(parents=True, exist_ok=True)
                
                # Move companion .lrc if exists
                old_lrc = file_path.with_suffix(".lrc")
                new_lrc = expected_dest.with_suffix(".lrc")
                if old_lrc.exists():
                    shutil.move(str(old_lrc), str(new_lrc))

                shutil.move(str(file_path), str(expected_dest))
                moved.append((file_path, expected_dest))

                # Clean up empty parent directories
                parent = file_path.parent
                while parent != target_dir and parent.exists():
                    if not any(parent.iterdir()):
                        parent.rmdir()
                        parent = parent.parent
                    else:
                        break

        return moved
