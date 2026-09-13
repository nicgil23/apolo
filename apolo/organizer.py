import os
import re
import shutil
from pathlib import Path
from typing import Optional, Tuple

from apolo.config import ApoloConfig, load_config
from apolo.metadata.models import TrackMetadata
from apolo.utils import (
    extract_disc_info,
    is_compilation_album,
    is_single_release,
    sanitize_filename,
)


class LibraryOrganizer:
    def __init__(self, config: Optional[ApoloConfig] = None):
        self.config = config or load_config()
        self.library_dir = self.config.directories.library_dir

    def _resolve_case_insensitive_dir(self, parent_dir: Path, target_name: str) -> Path:
        """Finds existing directory on disk matching target_name case-insensitively, or returns new path."""
        if not parent_dir.exists():
            return parent_dir / target_name
        try:
            for entry in parent_dir.iterdir():
                if entry.is_dir() and entry.name.lower() == target_name.lower():
                    return entry
        except Exception:
            pass
        return parent_dir / target_name

    def get_destination_path(self, metadata: TrackMetadata, extension: str = ".opus") -> Path:
        if not extension.startswith("."):
            extension = f".{extension}"
        artist_clean = sanitize_filename(metadata.get_album_artist_or_artist())
        track_artist_clean = sanitize_filename(metadata.artist or "Unknown Artist")
        raw_album = metadata.album or "Single"
        cleaned_album_name, disc_from_album = extract_disc_info(raw_album)
        album_clean = sanitize_filename(cleaned_album_name or raw_album)
        date_str = metadata.get_year()
        track_num = metadata.track_number if metadata.track_number is not None else 1
        title_clean = sanitize_filename(metadata.title)

        disc_num = metadata.disc_number or disc_from_album or 1
        disc_total = metadata.disc_total

        # Resolve case-matching artist directory to prevent FRO! vs Fro! splits
        artist_dir = self._resolve_case_insensitive_dir(self.library_dir, artist_clean)

        # 1. Compilation / Various Artists check
        is_compilation = bool(metadata.compilation) or is_compilation_album(raw_album, metadata.album_artist)
        if is_compilation and self.config.organization.various_artists_folder:
            folder_artist = self._resolve_case_insensitive_dir(self.library_dir, "Various Artists")
            album_folder = f"{album_clean} ({date_str})" if date_str and date_str != "Unknown Year" else album_clean
            resolved_album_dir = self._resolve_case_insensitive_dir(folder_artist, album_folder)
            file_name = f"{track_num:02d} - {track_artist_clean} - {title_clean}{extension}"

            has_existing_multi_disc = False
            if resolved_album_dir.exists():
                try:
                    has_existing_multi_disc = any(
                        e.is_dir() and re.match(r"^(disc|cd|vol(?:ume)?|part)\s*\d+", e.name, re.IGNORECASE)
                        for e in resolved_album_dir.iterdir()
                    )
                except Exception:
                    pass

            is_multi_disc = (
                (disc_total is not None and disc_total > 1)
                or disc_num > 1
                or disc_from_album is not None
                or has_existing_multi_disc
            )

            if is_multi_disc and self.config.organization.multi_disc_folder:
                dest_dir = self._resolve_case_insensitive_dir(resolved_album_dir, f"Disc {disc_num:02d}")
            else:
                dest_dir = resolved_album_dir
            return dest_dir / file_name

        # 2. Standalone Single check
        if self.config.organization.group_singles and is_single_release(raw_album, metadata.track_total):
            dest_dir = self._resolve_case_insensitive_dir(artist_dir, "Singles")
            if date_str and date_str != "Unknown Year":
                file_name = f"{title_clean} ({date_str}){extension}"
            else:
                file_name = f"{title_clean}{extension}"
            return dest_dir / file_name

        # 3. Studio / Multi-Track Album
        album_folder = f"{album_clean} ({date_str})" if date_str and date_str != "Unknown Year" else album_clean
        resolved_album_dir = self._resolve_case_insensitive_dir(artist_dir, album_folder)

        has_existing_multi_disc = False
        if resolved_album_dir.exists():
            try:
                has_existing_multi_disc = any(
                    e.is_dir() and re.match(r"^(disc|cd|vol(?:ume)?|part)\s*\d+", e.name, re.IGNORECASE)
                    for e in resolved_album_dir.iterdir()
                )
            except Exception:
                pass

        is_multi_disc = (
            (disc_total is not None and disc_total > 1)
            or disc_num > 1
            or disc_from_album is not None
            or has_existing_multi_disc
        )

        if is_multi_disc:
            if self.config.organization.multi_disc_folder:
                dest_dir = self._resolve_case_insensitive_dir(resolved_album_dir, f"Disc {disc_num:02d}")
                file_name = f"{track_num:02d} - {title_clean}{extension}"
            else:
                dest_dir = resolved_album_dir
                file_name = f"{disc_num}-{track_num:02d} - {title_clean}{extension}"
        else:
            dest_dir = resolved_album_dir
            file_name = f"{track_num:02d} - {title_clean}{extension}"

        return dest_dir / file_name

    def organize_track(self, source_audio: Path, metadata: TrackMetadata, extension: Optional[str] = None) -> Tuple[Path, Optional[Path]]:
        """
        Moves the audio file to its destination directory in the music library
        and creates a companion .lrc file if synced lyrics are present.
        Handles collisions safely according to configuration.
        Returns: (dest_audio_path, dest_lrc_path_or_None)
        """
        ext = extension or (source_audio.suffix if source_audio.suffix.lower() == ".flac" else ".opus")
        dest_audio = self.get_destination_path(metadata, extension=ext)
        dest_audio.parent.mkdir(parents=True, exist_ok=True)

        # Handle destination collisions
        if dest_audio.exists():
            # If same path as source, no need to move
            if dest_audio.resolve() == source_audio.resolve():
                pass
            elif self.config.organization.collision_strategy == "skip":
                # Check if identical in size
                if source_audio.exists() and dest_audio.stat().st_size == source_audio.stat().st_size:
                    source_audio.unlink()
            elif self.config.organization.collision_strategy == "rename":
                counter = 1
                base_stem = dest_audio.stem
                while dest_audio.exists():
                    dest_audio = dest_audio.with_name(f"{base_stem} ({counter}){dest_audio.suffix}")
                    counter += 1
                if source_audio.exists():
                    shutil.move(str(source_audio), str(dest_audio))
            else:  # overwrite
                dest_audio.unlink()
                if source_audio.exists():
                    shutil.move(str(source_audio), str(dest_audio))
        else:
            if source_audio.exists():
                shutil.move(str(source_audio), str(dest_audio))

        dest_lrc = None
        if self.config.organization.save_lrc_file and metadata.synced_lyrics:
            dest_lrc = dest_audio.with_suffix(".lrc")
            dest_lrc.write_text(metadata.synced_lyrics, encoding="utf-8")

        return dest_audio, dest_lrc
