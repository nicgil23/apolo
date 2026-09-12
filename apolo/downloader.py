import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yt_dlp

from apolo.config import ApoloConfig, load_config
from apolo.utils import clean_track_title


class AudioDownloader:
    def __init__(self, config: Optional[ApoloConfig] = None):
        self.config = config or load_config()
        self.temp_dir = self.config.directories.temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def download_url(self, url: str) -> List[Tuple[Path, str, Optional[str], Optional[float], Optional[str]]]:
        """
        Downloads URL using yt-dlp to best quality .opus audio.
        Returns a list of tuples: (file_path, extracted_title, extracted_artist, duration, thumbnail_url)
        """
        ydl_opts: Dict[str, Any] = {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": self.config.downloader.audio_format,
                    "preferredquality": self.config.downloader.audio_quality,
                }
            ],
            "outtmpl": str(self.temp_dir / "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
        }

        results = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return []

            # Handle playlists or single video
            entries = info.get("entries") if "entries" in info and info["entries"] else [info]

            for entry in entries:
                if not entry:
                    continue
                video_id = entry.get("id")
                raw_title = entry.get("title", "")
                raw_uploader = entry.get("artist") or entry.get("uploader") or entry.get("channel")
                duration = entry.get("duration")
                thumbnail = entry.get("thumbnail")

                # The postprocessor turns the file into .opus
                expected_file = self.temp_dir / f"{video_id}.{self.config.downloader.audio_format}"

                # Clean up title / artist
                cleaned_title, parsed_artist = clean_track_title(raw_title)
                artist = parsed_artist or raw_uploader

                if expected_file.exists():
                    results.append((expected_file, cleaned_title, artist, duration, thumbnail))

        return results
