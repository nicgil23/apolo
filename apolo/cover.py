import io
from pathlib import Path
from typing import List, Optional, Tuple
from PIL import Image

from apolo.pipeline import AUDIO_EXTENSIONS
from apolo.tagger import AudioTagger


class CoverManager:
    @staticmethod
    def optimize_image_bytes(image_data: bytes, max_dim: int = 1400) -> bytes:
        """Loads image, converts to RGB JPEG, resizes if larger than max_dim, and returns JPEG bytes."""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                img = img.convert("RGB")
                w, h = img.size
                if w > max_dim or h > max_dim:
                    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=92, optimize=True)
                return buf.getvalue()
        except Exception:
            return image_data

    @staticmethod
    def extract_covers(
        paths: List[Path],
        target_filename: str = "cover.jpg",
        overwrite: bool = False,
    ) -> List[Tuple[Path, Path]]:
        """
        Scans paths for audio files, extracts embedded cover art, and writes target_filename
        (e.g. cover.jpg or folder.jpg) to the containing directory.
        Returns: list of (audio_file_path, extracted_cover_path)
        """
        extracted = []
        seen_dirs = set()

        target_files: List[Path] = []
        for p in paths:
            if not p.exists():
                continue
            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
                target_files.append(p)
            elif p.is_dir():
                target_files.extend([f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS])

        target_files = sorted(list(set(target_files)))

        for f in target_files:
            parent_dir = f.parent
            cover_dest = parent_dir / target_filename
            if parent_dir in seen_dirs:
                continue

            if cover_dest.exists() and not overwrite:
                seen_dirs.add(parent_dir)
                continue

            cover_bytes = AudioTagger.extract_cover_art_from_file(f)
            if cover_bytes:
                try:
                    cover_dest.write_bytes(cover_bytes)
                    extracted.append((f, cover_dest))
                    seen_dirs.add(parent_dir)
                except Exception:
                    pass

        return extracted

    @staticmethod
    def set_album_cover(
        paths: List[Path],
        image_path: Path,
        optimize: bool = True,
    ) -> int:
        """
        Embeds the given image file as front cover art into all audio files in paths.
        Returns: number of updated tracks
        """
        if not image_path.exists() or not image_path.is_file():
            raise FileNotFoundError(f"Cover image file not found: {image_path}")

        raw_bytes = image_path.read_bytes()
        cover_data = CoverManager.optimize_image_bytes(raw_bytes) if optimize else raw_bytes

        target_files: List[Path] = []
        for p in paths:
            if not p.exists():
                continue
            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
                target_files.append(p)
            elif p.is_dir():
                target_files.extend([f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS])

        target_files = sorted(list(set(target_files)))
        updated_count = 0

        for f in target_files:
            if f.suffix.lower() in [".opus", ".flac"]:
                AudioTagger.update_tags(f, {}, cover_data=cover_data)
                updated_count += 1

        return updated_count
