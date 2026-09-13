import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import mutagen

from apolo.config import ApoloConfig, load_config
from apolo.pipeline import AUDIO_EXTENSIONS, ProcessingPipeline
from apolo.utils import format_duration, sanitize_filename


@dataclass
class PlaylistTrack:
    file_path: Path
    title: str
    artist: str
    duration: float = 0.0
    exists: bool = True


@dataclass
class PlaylistInfo:
    name: str
    file_path: Path
    total_tracks: int = 0
    valid_tracks: int = 0
    broken_tracks: int = 0
    total_duration: float = 0.0

    @property
    def formatted_duration(self) -> str:
        return format_duration(self.total_duration)


class PlaylistManager:
    def __init__(self, config: Optional[ApoloConfig] = None):
        self.config = config or load_config()
        self.library_dir = self.config.directories.library_dir
        self.playlists_dir = self.library_dir / "Playlists"
        self.pipeline = ProcessingPipeline(self.config)

    def ensure_playlists_dir(self) -> Path:
        self.playlists_dir.mkdir(parents=True, exist_ok=True)
        return self.playlists_dir

    def list_playlists(self) -> List[PlaylistInfo]:
        """Scans and analyzes all .m3u and .m3u8 playlist files in Playlists directory."""
        if not self.playlists_dir.exists():
            return []

        playlist_files = sorted(
            list(self.playlists_dir.glob("*.m3u8")) + list(self.playlists_dir.glob("*.m3u"))
        )
        results: List[PlaylistInfo] = []

        for pl_path in playlist_files:
            info = self.inspect_playlist(pl_path)
            results.append(info)

        return results

    def inspect_playlist(self, playlist_path: Path) -> PlaylistInfo:
        """Reads a playlist file and verifies track paths and durations."""
        info = PlaylistInfo(
            name=playlist_path.stem,
            file_path=playlist_path,
        )

        try:
            lines = playlist_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            return info

        for line in lines:
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue

            info.total_tracks += 1
            # Resolve track path (relative to playlist folder or absolute)
            track_path = (playlist_path.parent / line_str).resolve() if not os.path.isabs(line_str) else Path(line_str)
            if track_path.exists() and track_path.is_file():
                info.valid_tracks += 1
                try:
                    audio = mutagen.File(track_path)
                    if audio and audio.info:
                        info.total_duration += getattr(audio.info, "length", 0.0) or 0.0
                except Exception:
                    pass
            else:
                info.broken_tracks += 1

        return info

    def create_smart_playlist(
        self,
        name: str,
        genre: Optional[str] = None,
        year: Optional[str] = None,
        year_min: Optional[int] = None,
        year_max: Optional[int] = None,
        artist: Optional[str] = None,
        origin: Optional[str] = None,
        compilation: Optional[bool] = None,
    ) -> Tuple[Path, int]:
        """
        Creates an .m3u8 playlist in Playlists/ by querying tracks matching metadata filters.
        Returns: (playlist_path, track_count)
        """
        self.ensure_playlists_dir()
        all_tracks = sorted([
            p for p in self.library_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS and "Playlists" not in p.parts
        ])

        matched_tracks: List[Tuple[Path, str, str, float]] = []

        for p in all_tracks:
            info = self.pipeline.extract_file_info(p)
            track_title = info.get("title") or p.stem
            track_artist = info.get("artist") or "Unknown Artist"
            track_genre = info.get("genre") or ""
            track_date = str(info.get("date") or "")
            track_origin = str(info.get("origin") or "")
            track_comp = bool(info.get("compilation"))
            track_dur = float(info.get("duration") or 0.0)

            # 1. Genre filter
            if genre and genre.lower() not in track_genre.lower():
                continue

            # 2. Artist filter
            if artist and artist.lower() not in track_artist.lower():
                continue

            # 3. Origin filter
            if origin and origin.lower() != track_origin.lower():
                continue

            # 4. Compilation filter
            if compilation is not None and track_comp != compilation:
                continue

            # 5. Year / Date filters
            track_year_int = None
            if track_date:
                try:
                    track_year_int = int(track_date.split("-")[0].strip())
                except Exception:
                    pass

            if year:
                if ".." in year:
                    parts = year.split("..")
                    try:
                        ymin = int(parts[0])
                        ymax = int(parts[1])
                        if track_year_int is None or not (ymin <= track_year_int <= ymax):
                            continue
                    except Exception:
                        pass
                else:
                    if str(year) not in track_date:
                        continue

            if year_min is not None and (track_year_int is None or track_year_int < year_min):
                continue
            if year_max is not None and (track_year_int is None or track_year_int > year_max):
                continue

            matched_tracks.append((p, track_title, track_artist, track_dur))

        # Write M3U8
        clean_name = sanitize_filename(name)
        pl_path = self.playlists_dir / f"{clean_name}.m3u8"
        self._write_m3u8(pl_path, matched_tracks)

        return pl_path, len(matched_tracks)

    def create_manual_playlist(
        self,
        name: str,
        paths: List[Path],
    ) -> Tuple[Path, int]:
        """Creates a playlist from a list of files or directories."""
        self.ensure_playlists_dir()
        target_files: List[Path] = []
        for p in paths:
            if not p.exists():
                continue
            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
                target_files.append(p)
            elif p.is_dir():
                target_files.extend([
                    f for f in p.rglob("*")
                    if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS and "Playlists" not in f.parts
                ])

        target_files = sorted(list(set(target_files)))
        matched_tracks: List[Tuple[Path, str, str, float]] = []

        for f in target_files:
            info = self.pipeline.extract_file_info(f)
            title = info.get("title") or f.stem
            artist = info.get("artist") or "Unknown Artist"
            duration = float(info.get("duration") or 0.0)
            matched_tracks.append((f, title, artist, duration))

        clean_name = sanitize_filename(name)
        pl_path = self.playlists_dir / f"{clean_name}.m3u8"
        self._write_m3u8(pl_path, matched_tracks)

        return pl_path, len(matched_tracks)

    def _write_m3u8(self, pl_path: Path, tracks: List[Tuple[Path, str, str, float]]) -> None:
        """Writes an extended #EXTM3U file with relative file paths."""
        lines = ["#EXTM3U"]
        for path, title, artist, dur in tracks:
            try:
                rel_path = os.path.relpath(path, pl_path.parent)
            except Exception:
                rel_path = str(path)
            dur_int = int(dur) if dur else -1
            lines.append(f"#EXTINF:{dur_int},{artist} - {title}")
            lines.append(rel_path)

        pl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def repair_playlists(self) -> Dict[str, int]:
        """
        Scans all playlists for broken file links.
        Attempts to locate relocated audio files in library_dir by filename and rewrites playlists.
        Returns: {playlist_name: count_of_repaired_links}
        """
        if not self.playlists_dir.exists():
            return {}

        all_library_files = {
            p.name.lower(): p
            for p in self.library_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS and "Playlists" not in p.parts
        }

        playlist_files = sorted(
            list(self.playlists_dir.glob("*.m3u8")) + list(self.playlists_dir.glob("*.m3u"))
        )
        repaired_summary: Dict[str, int] = {}

        for pl_path in playlist_files:
            try:
                lines = pl_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue

            new_lines = []
            repaired_count = 0
            modified = False

            for line in lines:
                line_str = line.strip()
                if not line_str or line_str.startswith("#"):
                    new_lines.append(line)
                    continue

                track_path = (pl_path.parent / line_str).resolve() if not os.path.isabs(line_str) else Path(line_str)
                if track_path.exists():
                    new_lines.append(line)
                else:
                    # Broken link! Try to find by filename in library
                    file_name = Path(line_str).name.lower()
                    if file_name in all_library_files:
                        new_target = all_library_files[file_name]
                        try:
                            rel_new = os.path.relpath(new_target, pl_path.parent)
                        except Exception:
                            rel_new = str(new_target)
                        new_lines.append(rel_new)
                        repaired_count += 1
                        modified = True
                    else:
                        new_lines.append(line)

            if modified:
                pl_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
                repaired_summary[pl_path.name] = repaired_count

        return repaired_summary

    def export_playlist(
        self,
        name: str,
        dest_dir: Path,
        copy_files: bool = True,
    ) -> Tuple[Path, int]:
        """
        Exports a playlist to a target directory (e.g. SD Card, USB Drive).
        Copies audio tracks and creates a local playlist file.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        clean_name = sanitize_filename(name)
        pl_candidates = [
            self.playlists_dir / f"{name}.m3u8",
            self.playlists_dir / f"{clean_name}.m3u8",
            self.playlists_dir / f"{name}.m3u",
            self.playlists_dir / f"{clean_name}.m3u",
            Path(name),
        ]

        target_pl: Optional[Path] = None
        for cand in pl_candidates:
            if cand.exists() and cand.is_file():
                target_pl = cand
                break

        if not target_pl:
            raise FileNotFoundError(f"Playlist not found: {name}")

        lines = target_pl.read_text(encoding="utf-8", errors="replace").splitlines()
        exported_lines = ["#EXTM3U"]
        copied_count = 0

        for idx, line in enumerate(lines):
            line_str = line.strip()
            if not line_str:
                continue
            if line_str.startswith("#EXTINF"):
                exported_lines.append(line_str)
                continue
            if line_str.startswith("#"):
                continue

            track_path = (target_pl.parent / line_str).resolve() if not os.path.isabs(line_str) else Path(line_str)
            if track_path.exists() and track_path.is_file():
                dest_track = dest_dir / track_path.name
                if copy_files and not dest_track.exists():
                    shutil.copy2(str(track_path), str(dest_track))
                exported_lines.append(track_path.name)
                copied_count += 1

        exported_pl_path = dest_dir / f"{target_pl.stem}.m3u8"
        exported_pl_path.write_text("\n".join(exported_lines) + "\n", encoding="utf-8")

        return exported_pl_path, copied_count
