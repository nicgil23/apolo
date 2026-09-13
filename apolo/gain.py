import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple
from mutagen.oggopus import OggOpus

from apolo.config import ApoloConfig, load_config
from apolo.pipeline import AUDIO_EXTENSIONS


@dataclass
class LoudnessResult:
    file_path: Path
    integrated_lufs: float
    loudness_range: float
    true_peak_db: float
    target_lufs: float
    gain_db: float

    @property
    def r128_gain_q78(self) -> int:
        """Standard Opus RFC 7845 header / tag gain format: 256 * dB (8.8 fixed point)."""
        return int(round(self.gain_db * 256.0))

    @property
    def replaygain_peak_linear(self) -> float:
        """Peak amplitude linear (1.0 = 0 dBFS)."""
        return min(1.0, math.pow(10.0, self.true_peak_db / 20.0))


class LoudnessScanner:
    def __init__(self, config: Optional[ApoloConfig] = None):
        self.config = config or load_config()

    @staticmethod
    def scan_file(file_path: Path, target_lufs: float = -18.0) -> Optional[LoudnessResult]:
        """
        Analyzes audio loudness using ffmpeg ebur128 filter.
        Returns LoudnessResult with calculated gain against target_lufs.
        """
        if not file_path.exists():
            return None

        cmd = [
            "ffmpeg",
            "-nostats",
            "-i",
            str(file_path),
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=True)
            output = res.stderr
        except Exception:
            return None

        # Parse ffmpeg ebur128 summary output
        i_match = re.search(r"Integrated loudness:\s+I:\s+([-\d.]+)\s+LUFS", output)
        lra_match = re.search(r"Loudness range:\s+LRA:\s+([-\d.]+)\s+LU", output)
        tp_match = re.search(r"Peak:\s+True:\s+([-\d.]+)\s+dBFS", output)

        if not i_match:
            return None

        try:
            integrated_lufs = float(i_match.group(1))
            lra = float(lra_match.group(1)) if lra_match else 0.0
            true_peak = float(tp_match.group(1)) if tp_match else 0.0
        except ValueError:
            return None

        gain_db = round(target_lufs - integrated_lufs, 2)

        return LoudnessResult(
            file_path=file_path,
            integrated_lufs=integrated_lufs,
            loudness_range=lra,
            true_peak_db=true_peak,
            target_lufs=target_lufs,
            gain_db=gain_db,
        )

    @staticmethod
    def tag_file_gain(file_path: Path, result: LoudnessResult) -> None:
        """
        Embeds EBU R128 and ReplayGain Vorbis comments into an .opus file.
        """
        if not file_path.exists() or file_path.suffix.lower() != ".opus":
            return

        try:
            audio = OggOpus(file_path)
            if audio.tags is None:
                audio.add_tags()

            # 1. Standard Opus RFC 7845 R128 Vorbis Comments
            audio["R128_TRACK_GAIN"] = [str(result.r128_gain_q78)]
            audio["R128_TRACK_PEAK"] = [f"{result.true_peak_db:.2f} dBFS"]

            # 2. General ReplayGain Compatibility Tags
            gain_sign = "+" if result.gain_db >= 0 else ""
            audio["REPLAYGAIN_TRACK_GAIN"] = [f"{gain_sign}{result.gain_db:.2f} dB"]
            audio["REPLAYGAIN_TRACK_PEAK"] = [f"{result.replaygain_peak_linear:.6f}"]

            audio.save()
        except Exception:
            pass

    def scan_and_tag_paths(
        self,
        paths: List[Path],
        target_lufs: float = -18.0,
        dry_run: bool = False,
        on_progress: Optional[Callable[[str, str], None]] = None,
    ) -> List[Tuple[Path, LoudnessResult]]:
        """
        Scans all audio files in paths, computes loudness, and writes R128/ReplayGain tags.
        """
        target_files: List[Path] = []
        for p in paths:
            if not p.exists():
                continue
            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
                target_files.append(p)
            elif p.is_dir():
                target_files.extend([f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS])

        target_files = sorted(list(set(target_files)))
        results = []

        for idx, f in enumerate(target_files, 1):
            if on_progress:
                on_progress("scanning", f"Measuring loudness ({idx}/{len(target_files)}): {f.name}...")

            loud_res = self.scan_file(f, target_lufs=target_lufs)
            if loud_res:
                if not dry_run and f.suffix.lower() == ".opus":
                    self.tag_file_gain(f, loud_res)
                results.append((f, loud_res))

        return results
