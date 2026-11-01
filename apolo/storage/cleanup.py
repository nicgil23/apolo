from pathlib import Path

from apolo.constants import AUDIO_EXTENSIONS, IMAGE_EXTENSIONS, JUNK_EXTENSIONS, JUNK_NAMES


class StorageCleaner:
    @staticmethod
    def find_sidecar_lrc(file_path: Path) -> Path | None:
        """Finds companion .lrc file next to audio file."""
        if not file_path.parent.exists():
            return None
        lrc_candidate = file_path.with_suffix(".lrc")
        if lrc_candidate.exists() and lrc_candidate.is_file():
            return lrc_candidate
        try:
            for item in file_path.parent.iterdir():
                if (
                    item.is_file()
                    and item.suffix.lower() == ".lrc"
                    and item.stem.lower() == file_path.stem.lower()
                ):
                    return item
        except Exception:
            pass
        return None

    @staticmethod
    def find_companion_cover(file_path: Path) -> Path | None:
        """Finds track-specific or album cover image in the same directory."""
        parent = file_path.parent
        if not parent.exists() or not parent.is_dir():
            return None

        # 1. Exact track stem match: e.g. track.jpg, track.png
        for ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
            sidecar = file_path.with_suffix(ext)
            if sidecar.exists() and sidecar.is_file():
                return sidecar
        try:
            for item in parent.iterdir():
                if (
                    item.is_file()
                    and item.suffix.lower() in IMAGE_EXTENSIONS
                    and item.stem.lower() == file_path.stem.lower()
                ):
                    return item
        except Exception:
            pass

        # 2. Well-known cover image names in directory
        known_names = ["cover", "folder", "front", "album", "artwork", "art"]
        for name in known_names:
            for ext in [".jpg", ".jpeg", ".png", ".webp", ".bmp"]:
                candidate = parent / f"{name}{ext}"
                if candidate.exists() and candidate.is_file():
                    return candidate
        try:
            for item in parent.iterdir():
                if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS:
                    if item.stem.lower() in known_names:
                        return item
        except Exception:
            pass

        # 3. If there is only one image in the directory, use it
        try:
            images = [
                item
                for item in parent.iterdir()
                if item.is_file() and item.suffix.lower() in IMAGE_EXTENSIONS
            ]
            if len(images) == 1:
                return images[0]
        except Exception:
            pass

        return None

    @staticmethod
    def cleanup_source_file_artifacts(file_path: Path) -> None:
        """Deletes track-specific sidecar files (.lrc, .jpg/.png) associated with file_path."""
        sidecar_lrc = StorageCleaner.find_sidecar_lrc(file_path)
        if sidecar_lrc and sidecar_lrc.exists():
            try:
                sidecar_lrc.unlink()
            except Exception:
                pass

        for ext in IMAGE_EXTENSIONS:
            img_sidecar = file_path.with_suffix(ext)
            if img_sidecar.exists() and img_sidecar.is_file():
                try:
                    img_sidecar.unlink()
                except Exception:
                    pass
        if file_path.parent.exists():
            try:
                for item in file_path.parent.iterdir():
                    if (
                        item.is_file()
                        and item.suffix.lower() in IMAGE_EXTENSIONS
                        and item.stem.lower() == file_path.stem.lower()
                    ):
                        item.unlink()
            except Exception:
                pass

    @staticmethod
    def cleanup_processed_directory(
        dir_path: Path,
        root_boundary: Path | None = None,
        protected_dirs: set[Path] | None = None,
    ) -> None:
        """
        Cleans up leftover images, lyrics, and junk files in dir_path if no audio files remain,
        and removes empty directories up to root_boundary.
        """
        if not dir_path.exists() or not dir_path.is_dir():
            return

        # Check if any audio files still exist in this directory or subdirectories
        remaining_audio = [
            p for p in dir_path.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
        ]
        if remaining_audio:
            return

        # Delete remaining image files, .lrc files, and junk files in dir_path
        try:
            for item in list(dir_path.rglob("*")):
                if item.is_file():
                    ext = item.suffix.lower()
                    name = item.name.lower()
                    if (
                        ext in IMAGE_EXTENSIONS
                        or ext == ".lrc"
                        or ext in JUNK_EXTENSIONS
                        or name in JUNK_NAMES
                    ):
                        try:
                            item.unlink()
                        except Exception:
                            pass
        except Exception:
            pass

        # Remove empty subdirectories bottom-up
        try:
            subdirs = sorted(
                [d for d in dir_path.rglob("*") if d.is_dir()],
                key=lambda p: len(p.parts),
                reverse=True,
            )
            for sub in subdirs:
                if sub.exists() and not any(sub.iterdir()):
                    try:
                        sub.rmdir()
                    except Exception:
                        pass
        except Exception:
            pass

        # Remove dir_path itself if not root_boundary and not in protected_dirs
        special_dirs = set()
        if protected_dirs:
            for p in protected_dirs:
                if p and p.exists():
                    special_dirs.add(p.resolve())
        if root_boundary and root_boundary.exists():
            special_dirs.add(root_boundary.resolve())

        curr = dir_path
        while curr.exists() and curr.resolve() not in special_dirs:
            try:
                if not any(curr.iterdir()):
                    parent = curr.parent
                    curr.rmdir()
                    curr = parent
                else:
                    break
            except Exception:
                break
