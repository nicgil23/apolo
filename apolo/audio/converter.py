import subprocess
from pathlib import Path

from apolo.config import ApoloConfig, load_config
from apolo.system import SystemEnvironment


class AudioConverter:
    def __init__(self, config: ApoloConfig | None = None):
        self.config = config or load_config()

    @staticmethod
    def is_ffmpeg_available() -> bool:
        return SystemEnvironment.check_ffmpeg()

    def convert_to_opus(self, input_file: Path) -> Path:
        """
        Converts any audio/video file to .opus in temp_dir using ffmpeg at maximum perceptible quality.
        Uses libopus with VBR, compression level 10, and 48kHz audio resample.
        """
        if input_file.suffix.lower() == ".opus":
            return input_file

        ffmpeg_bin = SystemEnvironment.require_binary("ffmpeg")

        output_file = self.config.directories.temp_dir / f"{input_file.stem}.opus"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        bitrate = getattr(self.config.downloader, "audio_bitrate", "256k")
        cmd = [
            str(ffmpeg_bin),
            "-y",
            "-i",
            str(input_file),
            "-vn",
            "-c:a",
            "libopus",
            "-b:a",
            bitrate,
            "-vbr",
            "on",
            "-compression_level",
            "10",
            "-ar",
            "48000",
            str(output_file),
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return output_file
