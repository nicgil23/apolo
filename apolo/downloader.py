import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import yt_dlp

from apolo.config import ApoloConfig, load_config
from apolo.utils import clean_media_url, clean_track_title, extract_primary_artist


@dataclass
class DownloadedTrackInfo:
    file_path: Path
    title: str
    artist: Optional[str] = None
    album_artist: Optional[str] = None
    album: Optional[str] = None
    track_number: Optional[int] = None
    track_total: Optional[int] = None
    release_date: Optional[str] = None
    duration: Optional[float] = None
    thumbnail_url: Optional[str] = None
    origin: Optional[str] = None


class AudioDownloader:
    def __init__(self, config: Optional[ApoloConfig] = None):
        self.config = config or load_config()
        self.temp_dir = self.config.directories.temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def download_url(
        self,
        url: str,
        origin: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> List[DownloadedTrackInfo]:
        """
        Downloads URL using yt-dlp to best quality .opus audio.
        Returns a list of DownloadedTrackInfo objects containing rich source metadata.
        """
        clean_url = clean_media_url(url)
        is_explicit_playlist = "/playlist" in clean_url and "list=" in clean_url

        def yt_progress_hook(d: dict) -> None:
            if cancel_check and cancel_check():
                raise RuntimeError("Download cancelled by user")

            if d.get("status") == "downloading" and progress_callback:
                downloaded = d.get("downloaded_bytes", 0)
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                percent_str = (d.get("_percent_str") or "").strip()
                if total and total > 0:
                    pct = round((downloaded / total) * 100.0, 1)
                    progress_callback(pct, f"{pct}%")
                elif percent_str:
                    clean_pct = re.sub(r"[^\d.]", "", percent_str)
                    val = float(clean_pct) if clean_pct else 50.0
                    progress_callback(val, percent_str)

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
            "noplaylist": not is_explicit_playlist,
            "sleep_interval_requests": 1.0,
            "progress_hooks": [yt_progress_hook],
        }

        results: List[DownloadedTrackInfo] = []
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=True)
            if not info:
                return []

            # Determine origin/source
            inferred_origin = origin
            if not inferred_origin:
                extractor = (info.get("extractor") or "").lower()
                if "youtube" in extractor or "youtu" in url.lower():
                    inferred_origin = "youtube"
                elif "soundcloud" in extractor or "soundcloud" in url.lower():
                    inferred_origin = "soundcloud"
                elif extractor:
                    inferred_origin = extractor
                else:
                    inferred_origin = "download"

            # Handle playlists or single video
            is_playlist = "entries" in info and info["entries"]
            entries = info["entries"] if is_playlist else [info]
            total_entries = len(entries) if is_playlist else None

            # Playlist album name fallback
            playlist_title = info.get("title", "")
            cleaned_playlist_album = None
            if playlist_title:
                cleaned_playlist_album = re.sub(r"^(Album|EP|Single)\s*-\s*", "", playlist_title, flags=re.IGNORECASE).strip()

            for idx, entry in enumerate(entries, 1):
                if not entry:
                    continue
                video_id = entry.get("id")
                raw_title = entry.get("title", "")
                raw_track = entry.get("track")
                raw_artist = entry.get("artist") or entry.get("uploader") or entry.get("channel")
                artists_list = entry.get("artists")
                raw_album = entry.get("album") or cleaned_playlist_album
                raw_album_artist = entry.get("album_artist")
                duration = entry.get("duration")
                thumbnail = entry.get("thumbnail")

                # Track and disc numbering
                track_num = entry.get("track_number") or entry.get("playlist_index") or (idx if is_playlist and total_entries and total_entries > 1 else None)
                track_total = entry.get("n_entries") or total_entries

                # Release date formatting (YYYYMMDD -> YYYY-MM-DD or YYYY)
                raw_date = entry.get("release_date") or entry.get("upload_date")
                formatted_date = None
                if raw_date and len(str(raw_date)) == 8:
                    s = str(raw_date)
                    formatted_date = f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
                elif entry.get("release_year"):
                    formatted_date = str(entry.get("release_year"))

                # Determine primary album artist
                if not raw_album_artist:
                    if artists_list and isinstance(artists_list, list) and len(artists_list) > 0:
                        raw_album_artist = artists_list[0]
                    else:
                        raw_album_artist = extract_primary_artist(raw_artist)

                # The postprocessor turns the file into .opus
                expected_file = self.temp_dir / f"{video_id}.{self.config.downloader.audio_format}"

                # Clean up title / artist
                cleaned_title, parsed_artist = clean_track_title(raw_title)
                final_title = raw_track or cleaned_title
                final_artist = parsed_artist or raw_artist

                if expected_file.exists():
                    results.append(
                        DownloadedTrackInfo(
                            file_path=expected_file,
                            title=final_title,
                            artist=final_artist,
                            album_artist=raw_album_artist or final_artist,
                            album=raw_album or "Single",
                            track_number=int(track_num) if track_num is not None else None,
                            track_total=int(track_total) if track_total is not None else None,
                            release_date=formatted_date,
                            duration=duration,
                            thumbnail_url=thumbnail,
                            origin=inferred_origin,
                        )
                    )

        return results

