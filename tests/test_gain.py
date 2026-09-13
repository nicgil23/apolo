import subprocess
from pathlib import Path
import pytest
from mutagen.oggopus import OggOpus
from typer.testing import CliRunner

from apolo.cli import app
from apolo.gain import LoudnessScanner
from apolo.metadata.models import TrackMetadata
from apolo.tagger import AudioTagger


def create_dummy_opus(output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1",
        "-c:a",
        "libopus",
        "-b:a",
        "128k",
        str(output_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    meta = TrackMetadata(title="Sine Wave", artist="Test Artist", album="Test Album")
    AudioTagger.tag_opus(output_path, meta)


def test_loudness_scanner_and_r128_tagging(tmp_path):
    opus_file = tmp_path / "sine.opus"
    create_dummy_opus(opus_file)

    loud_res = LoudnessScanner.scan_file(opus_file, target_lufs=-18.0)
    assert loud_res is not None
    assert isinstance(loud_res.integrated_lufs, float)
    assert isinstance(loud_res.gain_db, float)

    # Tag file with gain
    LoudnessScanner.tag_file_gain(opus_file, loud_res)

    audio = OggOpus(opus_file)
    assert "R128_TRACK_GAIN" in audio
    assert "REPLAYGAIN_TRACK_GAIN" in audio
    assert "REPLAYGAIN_TRACK_PEAK" in audio


def test_gain_cli_command(tmp_path):
    runner = CliRunner()
    opus_file = tmp_path / "sine_cli.opus"
    create_dummy_opus(opus_file)

    result = runner.invoke(app, ["gain", str(opus_file), "--target-lufs", "-18"])
    assert result.exit_code == 0
    assert "Loudness Analysis" in result.stdout
    assert "LUFS" in result.stdout
