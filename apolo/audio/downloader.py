import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yt_dlp

from apolo.config import ApoloConfig, load_config
from apolo.utils import clean_media_url, clean_track_title, extract_primary_artist

RETRY_DELAY_SECONDS = 10.0
MAX_DOWNLOAD_RETRIES = 3


@dataclass
class DownloadedTrackInfo:
    file_path: Path
    title: str
    artist: str | None = None
    album_artist: str | None = None
    album: str | None = None
    track_number: int | None = None
    track_total: int | None = None
    release_date: str | None = None
    duration: float | None = None
    thumbnail_url: str | None = None
    origin: str | None = None
    subtrack_id: str | None = None


class AudioDownloader:
    def __init__(self, config: ApoloConfig | None = None):
        self.config = config or load_config()
        self.temp_dir = self.config.directories.temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _wait_delay(seconds: float, cancel_check: Callable[[], bool] | None = None) -> None:
        """Sleeps for specified seconds while periodically checking for cancellation."""
        start = time.time()
        while time.time() - start < seconds:
            if cancel_check and cancel_check():
                raise RuntimeError("Download cancelled by user")
            time.sleep(0.25)

    def _parse_entry_to_track_info(
        self,
        entry: dict,
        expected_file: Path,
        idx: int,
        total_entries: int | None,
        cleaned_playlist_album: str | None,
        inferred_origin: str | None,
        subtrack_id: str | None = None,
    ) -> DownloadedTrackInfo:
        raw_title = entry.get("title", "")
        raw_track = entry.get("track")
        raw_artist = entry.get("artist") or entry.get("uploader") or entry.get("channel")
        artists_list = entry.get("artists")
        raw_album = entry.get("album") or cleaned_playlist_album
        raw_album_artist = entry.get("album_artist")
        duration = entry.get("duration")
        thumbnail = entry.get("thumbnail")

        # Track and disc numbering
        track_num = (
            entry.get("track_number")
            or entry.get("playlist_index")
            or (idx if total_entries and total_entries > 1 else None)
        )
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

        # Clean up title / artist
        cleaned_title, parsed_artist = clean_track_title(raw_title)
        final_title = raw_track or cleaned_title
        final_artist = parsed_artist or raw_artist

        if not raw_album or raw_album.strip().lower() in ["single", "singles", "unknown album"]:
            album_val = f"{final_title} - Single" if final_title else "Single"
        else:
            album_val = raw_album

        return DownloadedTrackInfo(
            file_path=expected_file,
            title=final_title,
            artist=final_artist,
            album_artist=raw_album_artist or final_artist,
            album=album_val,
            track_number=int(track_num) if track_num is not None else None,
            track_total=int(track_total) if track_total is not None else None,
            release_date=formatted_date,
            duration=duration,
            thumbnail_url=thumbnail,
            origin=inferred_origin,
            subtrack_id=subtrack_id,
        )

    def download_url(
        self,
        url: str,
        origin: str | None = None,
        suggested_title: str | None = None,
        progress_callback: Callable[[float, str], None] | None = None,
        cancel_check: Callable[[], bool] | None = None,
        on_playlist_init: Callable[[str, int, list[dict[str, Any]]], None] | None = None,
        on_subtrack_status: Callable[[str, str, str | None, int, float | None], None] | None = None,
        on_subtrack_progress: Callable[[str, float, str], None] | None = None,
        on_active_track: Callable[[int, int, str, str | None, float, str], None] | None = None,
        on_track_title: Callable[[str], None] | None = None,
    ) -> list[DownloadedTrackInfo]:
        """
        Downloads URL using yt-dlp to best quality audio (.opus).
        Supports playlist decomposition with subtrack progress and automatic 10-second retries on failure.
        """
        clean_url = clean_media_url(url)
        is_explicit_playlist = ("/playlist" in clean_url and "list=" in clean_url) or (
            "list=OLAK5uy_" in clean_url
        )

        # Normalize music.youtube.com playlist/album to standard youtube.com playlist to avoid yt-dlp extractor issues
        fetch_url = clean_url
        if "music.youtube.com" in fetch_url and "list=" in fetch_url:
            fetch_url = fetch_url.replace("music.youtube.com", "www.youtube.com")

        # First, attempt flat extraction to inspect if it's a playlist or album
        extract_opts: dict[str, Any] = {
            "extract_flat": "in_playlist",
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": not is_explicit_playlist,
        }

        extracted_info = None
        try:
            with yt_dlp.YoutubeDL(extract_opts) as ydl_flat:
                extracted_info = ydl_flat.extract_info(fetch_url, download=False)
        except Exception:
            extracted_info = None

        raw_entries = []
        if extracted_info and extracted_info.get("entries") is not None:
            try:
                raw_entries = [e for e in list(extracted_info["entries"]) if e]
            except Exception:
                raw_entries = []

        is_playlist = (
            extracted_info is not None
            and (
                is_explicit_playlist
                or extracted_info.get("_type") in ("playlist", "multi_video")
                or len(raw_entries) > 1
            )
            and len(raw_entries) > 0
        )

        if is_playlist and extracted_info:
            playlist_title = extracted_info.get("title", "")
            cleaned_playlist_album = None
            if playlist_title:
                cleaned_playlist_album = re.sub(
                    r"^(Album|EP|Single|Playlist)\s*-\s*", "", playlist_title, flags=re.IGNORECASE
                ).strip()

            display_title = (
                cleaned_playlist_album or playlist_title or suggested_title or "Playlist"
            )
            total_tracks = len(raw_entries)

            # Build subtrack metadata structures
            subtracks_data: list[dict[str, Any]] = []
            for idx, entry in enumerate(raw_entries, 1):
                sub_id = entry.get("id") or f"track_{idx}"
                raw_t = entry.get("title") or f"Track {idx}"
                raw_a = entry.get("artist") or entry.get("uploader") or entry.get("channel") or ""
                cl_title, cl_artist = clean_track_title(raw_t)
                subtracks_data.append(
                    {
                        "id": sub_id,
                        "title": cl_title or raw_t,
                        "artist": cl_artist or raw_a,
                        "status": "queued",
                        "progress": 0.0,
                        "progress_text": "En cola",
                        "track_number": idx,
                        "error": None,
                        "retry_count": 0,
                        "next_retry_at": None,
                    }
                )

            if on_playlist_init:
                on_playlist_init(display_title, total_tracks, subtracks_data)

            inferred_origin = origin
            if not inferred_origin:
                extractor = (extracted_info.get("extractor") or "").lower()
                if "youtube" in extractor or "youtu" in url.lower():
                    inferred_origin = "youtube"
                elif "soundcloud" in extractor or "soundcloud" in url.lower():
                    inferred_origin = "soundcloud"
                else:
                    inferred_origin = "download"

            results: list[DownloadedTrackInfo] = []
            completed_count = 0
            failed_count = 0

            # Download and process each entry individually with retries
            for idx, entry in enumerate(raw_entries, 1):
                if cancel_check and cancel_check():
                    raise RuntimeError("Download cancelled by user")

                video_id = entry.get("id")
                entry_url = entry.get("url") or (
                    f"https://www.youtube.com/watch?v={video_id}" if video_id else None
                )
                if not entry_url and video_id:
                    entry_url = video_id
                if not entry_url:
                    continue

                sub_id = subtracks_data[idx - 1]["id"]
                sub_title = subtracks_data[idx - 1]["title"]
                sub_artist = subtracks_data[idx - 1]["artist"]
                current_sub_progress = 0.0

                if on_active_track:
                    on_active_track(idx, total_tracks, sub_title, sub_artist, 0.0, "0%")

                def entry_progress_hook(d: dict) -> None:
                    nonlocal current_sub_progress
                    if cancel_check and cancel_check():
                        raise RuntimeError("Download cancelled by user")

                    if d.get("status") == "downloading":
                        downloaded = d.get("downloaded_bytes", 0)
                        total = d.get("total_bytes") or d.get("total_bytes_estimate")
                        percent_str = (d.get("_percent_str") or "").strip()
                        pct = 0.0
                        if total and total > 0:
                            pct = round((downloaded / total) * 100.0, 1)
                        elif percent_str:
                            clean_pct = re.sub(r"[^\d.]", "", percent_str)
                            pct = float(clean_pct) if clean_pct else 50.0

                        current_sub_progress = pct
                        if on_subtrack_progress:
                            on_subtrack_progress(sub_id, pct, f"{pct}%")

                        if on_active_track:
                            on_active_track(
                                idx, total_tracks, sub_title, sub_artist, pct, f"{pct}%"
                            )

                        if progress_callback:
                            overall_pct = round(
                                ((completed_count + (pct / 100.0)) / total_tracks) * 100.0, 1
                            )
                            progress_callback(
                                overall_pct,
                                f"{completed_count}/{total_tracks} ({overall_pct}%)",
                            )

                single_ydl_opts: dict[str, Any] = {
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
                    "noplaylist": True,
                    "sleep_interval_requests": 0.5,
                    "progress_hooks": [entry_progress_hook],
                }

                for attempt in range(MAX_DOWNLOAD_RETRIES + 1):
                    if cancel_check and cancel_check():
                        raise RuntimeError("Download cancelled by user")

                    if on_subtrack_status:
                        on_subtrack_status(sub_id, "downloading", None, attempt, None)

                    try:
                        with yt_dlp.YoutubeDL(single_ydl_opts) as single_ydl:
                            full_info = single_ydl.extract_info(entry_url, download=True)

                        vid_id = (full_info.get("id") if full_info else None) or video_id
                        expected_file = (
                            self.temp_dir / f"{vid_id}.{self.config.downloader.audio_format}"
                        )

                        if expected_file.exists():
                            item_info = full_info or entry
                            track_item = self._parse_entry_to_track_info(
                                item_info,
                                expected_file,
                                idx=idx,
                                total_entries=total_tracks,
                                cleaned_playlist_album=cleaned_playlist_album,
                                inferred_origin=inferred_origin,
                                subtrack_id=sub_id,
                            )
                            results.append(track_item)
                            completed_count += 1

                            if on_subtrack_status:
                                on_subtrack_status(sub_id, "completed", None, attempt, None)

                            if on_active_track:
                                on_active_track(
                                    idx, total_tracks, sub_title, sub_artist, 100.0, "Listo"
                                )

                            if progress_callback:
                                overall_pct = round((completed_count / total_tracks) * 100.0, 1)
                                progress_callback(
                                    overall_pct,
                                    f"{completed_count}/{total_tracks} ({overall_pct}%)",
                                )
                            break
                        else:
                            raise FileNotFoundError(
                                f"Downloaded audio file not found: {expected_file}"
                            )

                    except Exception as e:
                        if cancel_check and cancel_check():
                            raise RuntimeError("Download cancelled by user")

                        err_msg = str(e)
                        if attempt < MAX_DOWNLOAD_RETRIES:
                            next_retry = time.time() + RETRY_DELAY_SECONDS
                            if on_subtrack_status:
                                on_subtrack_status(
                                    sub_id,
                                    "retrying",
                                    f"Fallo. Reintentando en 10s: {err_msg}",
                                    attempt + 1,
                                    next_retry,
                                )
                            self._wait_delay(RETRY_DELAY_SECONDS, cancel_check=cancel_check)
                        else:
                            failed_count += 1
                            if on_subtrack_status:
                                on_subtrack_status(
                                    sub_id,
                                    "failed",
                                    f"Error tras reintentos: {err_msg}",
                                    attempt + 1,
                                    None,
                                )

            return results

        # Single Track Download (or standard direct download) with 10-second retry loop
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

        ydl_opts: dict[str, Any] = {
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

        last_error = None
        for attempt in range(MAX_DOWNLOAD_RETRIES + 1):
            if cancel_check and cancel_check():
                raise RuntimeError("Download cancelled by user")

            try:
                results: list[DownloadedTrackInfo] = []
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

                    raw_title = info.get("title", "")
                    cleaned_t, parsed_a = clean_track_title(raw_title)
                    display_single = f"{parsed_a} - {cleaned_t}" if parsed_a else cleaned_t
                    if on_track_title and display_single:
                        on_track_title(display_single)

                    entries = info.get("entries") or [info]
                    total_entries = len(entries)

                    playlist_title = info.get("title", "")
                    cleaned_playlist_album = None
                    if playlist_title and total_entries > 1:
                        cleaned_playlist_album = re.sub(
                            r"^(Album|EP|Single)\s*-\s*", "", playlist_title, flags=re.IGNORECASE
                        ).strip()

                    for idx, entry in enumerate(entries, 1):
                        if not entry:
                            continue
                        video_id = entry.get("id")
                        expected_file = (
                            self.temp_dir / f"{video_id}.{self.config.downloader.audio_format}"
                        )
                        if expected_file.exists():
                            results.append(
                                self._parse_entry_to_track_info(
                                    entry,
                                    expected_file,
                                    idx=idx,
                                    total_entries=total_entries if total_entries > 1 else None,
                                    cleaned_playlist_album=cleaned_playlist_album,
                                    inferred_origin=inferred_origin,
                                )
                            )

                if results:
                    return results
                else:
                    raise FileNotFoundError("Audio file extraction failed")

            except Exception as e:
                last_error = e
                if cancel_check and cancel_check():
                    raise RuntimeError("Download cancelled by user")

                if attempt < MAX_DOWNLOAD_RETRIES:
                    if progress_callback:
                        progress_callback(
                            0.0,
                            f"Error. Reintentando en 10s (intento {attempt + 1}/{MAX_DOWNLOAD_RETRIES})...",
                        )
                    self._wait_delay(RETRY_DELAY_SECONDS, cancel_check=cancel_check)
                else:
                    raise last_error

        return []
