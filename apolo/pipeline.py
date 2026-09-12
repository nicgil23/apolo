import os
import subprocess
from pathlib import Path
from typing import Callable, List, Optional, Tuple
import mutagen

from apolo.config import ApoloConfig, load_config
from apolo.downloader import AudioDownloader
from apolo.lyrics.lrclib import LRCLIBProvider
from apolo.metadata.matcher import MetadataMatcher
from apolo.metadata.models import TrackMetadata
from apolo.organizer import LibraryOrganizer
from apolo.tagger import AudioTagger
from apolo.utils import clean_track_title

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

        for opus_file, raw_title, raw_artist, duration, thumbnail_url in downloaded_items:
            search_query = f"{raw_artist} {raw_title}" if raw_artist else raw_title

            if on_progress:
                on_progress("matching", f"Searching metadata for '{search_query}'...")

            match = self.matcher.find_best_match(
                query=search_query,
                expected_title=raw_title,
                expected_artist=raw_artist,
                expected_duration=duration,
            )

            if not match:
                match = TrackMetadata(
                    title=raw_title or "Unknown Title",
                    artist=raw_artist or "Unknown Artist",
                    album="Single",
                    duration=duration,
                )

            if on_progress:
                on_progress("lyrics", f"Fetching synced lyrics for '{match.artist} - {match.title}'...")

            synced_lyrics = self.lyrics_provider.get_synced_lyrics(
                track_name=match.title,
                artist_name=match.artist,
                album_name=match.album,
                duration=match.duration or duration,
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

    def extract_file_info(self, file_path: Path) -> tuple[str, Optional[str], Optional[float]]:
        """Extract existing title, artist, duration from file metadata or filename."""
        raw_title = None
        raw_artist = None
        duration = None

        try:
            audio = mutagen.File(file_path)
            if audio is not None:
                duration = getattr(audio.info, "length", None)
                tags = getattr(audio, "tags", None)
                if tags:
                    if "TITLE" in tags:
                        raw_title = str(tags["TITLE"][0])
                    elif "title" in tags:
                        raw_title = str(tags["title"][0])
                    if "ARTIST" in tags:
                        raw_artist = str(tags["ARTIST"][0])
                    elif "artist" in tags:
                        raw_artist = str(tags["artist"][0])
        except Exception:
            pass

        if not raw_title:
            cleaned_title, parsed_artist = clean_track_title(file_path.stem)
            raw_title = cleaned_title
            if not raw_artist:
                raw_artist = parsed_artist

        return raw_title, raw_artist, duration

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

        raw_title, raw_artist, duration = self.extract_file_info(file_path)
        search_query = f"{raw_artist} {raw_title}" if raw_artist else raw_title

        if on_progress:
            on_progress("matching", f"Searching metadata for '{search_query}'...")

        match = self.matcher.find_best_match(
            query=search_query,
            expected_title=raw_title,
            expected_artist=raw_artist,
            expected_duration=duration,
        )

        if not match:
            match = TrackMetadata(
                title=raw_title or file_path.stem,
                artist=raw_artist or "Unknown Artist",
                album="Single",
                duration=duration,
            )

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

        for file_path in files:
            res = self.process_file(file_path, on_progress=on_progress)
            if res:
                results.append(res)

        return results
