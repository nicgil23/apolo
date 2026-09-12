import os
import shutil
from pathlib import Path
from typing import Optional, Tuple

from apolo.config import ApoloConfig, load_config
from apolo.metadata.models import TrackMetadata
from apolo.utils import sanitize_filename


class LibraryOrganizer:
    def __init__(self, config: Optional[ApoloConfig] = None):
        self.config = config or load_config()
        self.library_dir = self.config.directories.library_dir

    def get_destination_path(self, metadata: TrackMetadata) -> Path:
        artist_clean = sanitize_filename(metadata.get_album_artist_or_artist())
        album_clean = sanitize_filename(metadata.album or "Single")
        date_str = metadata.get_year()
        track_num = metadata.track_number if metadata.track_number is not None else 1
        title_clean = sanitize_filename(metadata.title)

        if date_str and date_str != "Unknown Year":
            folder_name = f"{album_clean} ({date_str})"
        else:
            folder_name = album_clean

        file_name = f"{track_num:02d} - {title_clean}.opus"

        dest_dir = self.library_dir / artist_clean / folder_name
        return dest_dir / file_name

    def organize_track(self, source_audio: Path, metadata: TrackMetadata) -> Tuple[Path, Optional[Path]]:
        """
        Moves the audio file to its destination directory in the music library
        and creates a companion .lrc file if synced lyrics are present.
        Returns: (dest_audio_path, dest_lrc_path_or_None)
        """
        dest_audio = self.get_destination_path(metadata)
        dest_audio.parent.mkdir(parents=True, exist_ok=True)

        # Move audio file (overwrite if destination exists or replace)
        if dest_audio.exists():
            dest_audio.unlink()
        shutil.move(str(source_audio), str(dest_audio))

        dest_lrc = None
        if self.config.organization.save_lrc_file and metadata.synced_lyrics:
            dest_lrc = dest_audio.with_suffix(".lrc")
            dest_lrc.write_text(metadata.synced_lyrics, encoding="utf-8")

        return dest_audio, dest_lrc
