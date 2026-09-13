import subprocess
from pathlib import Path
from rich.console import Console
import pytest

from apolo.inspector import inspect_track


def create_dummy_audio(path: Path, codec: str = "libopus", ext: str = ".opus"):
    """Creates a real audio file using ffmpeg."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:duration=2",
            "-c:a",
            codec,
            str(path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )


def test_inspect_track_with_dynamic_bitrate(tmp_path: Path):
    audio_file = tmp_path / "test_song.opus"
    create_dummy_audio(audio_file, codec="libopus", ext=".opus")

    console = Console(record=True)
    inspect_track(audio_file, console=console)
    output = console.export_text()

    assert "Metadata Inspector: test_song.opus" in output
    assert "Audio Specs" in output
    assert "Duration: 00:02" in output
    assert "Bitrate:" in output
    # Bitrate should not be empty / '-'
    assert "kbps" in output


def test_inspect_track_flac_bits_per_sample(tmp_path: Path):
    flac_file = tmp_path / "audiophile.flac"
    create_dummy_audio(flac_file, codec="flac", ext=".flac")

    console = Console(record=True)
    inspect_track(flac_file, console=console)
    output = console.export_text()

    assert "Metadata Inspector: audiophile.flac" in output
    assert "FLAC" in output
    assert "Bitrate:" in output
    assert "kbps" in output
    assert "Hz" in output
