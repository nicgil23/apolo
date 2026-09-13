import io
import subprocess
from pathlib import Path
from PIL import Image
import pytest
from typer.testing import CliRunner

from apolo.cli import app
from apolo.config import ApoloConfig, DirectoriesConfig, DownloaderConfig
from apolo.pipeline import ProcessingPipeline
from apolo.tagger import AudioTagger
from apolo.metadata.models import TrackMetadata


def create_dummy_opus(output_path: Path, title: str = "Test Track", artist: str = "Test Artist"):
    """Generates a 1-second silence Opus file with basic metadata."""
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=48000:cl=stereo",
        "-t",
        "1",
        "-c:a",
        "libopus",
        "-b:a",
        "128k",
        str(output_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    meta = TrackMetadata(
        title=title,
        artist=artist,
        album="Test Album",
        date="2024",
        track_number=1,
    )
    AudioTagger.tag_opus(output_path, meta)


def test_dry_run_process_file(tmp_path):
    library_dir = tmp_path / "Music"
    temp_dir = tmp_path / "temp"
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=library_dir, temp_dir=temp_dir),
    )
    pipeline = ProcessingPipeline(config)

    source_opus = tmp_path / "01 - Test Song.opus"
    create_dummy_opus(source_opus, title="Test Song", artist="Test Artist")

    res = pipeline.process_file(source_opus, dry_run=True)
    assert res is not None
    dest_audio, dest_lrc, meta = res

    # Source file MUST NOT be deleted in dry-run
    assert source_opus.exists()

    # Destination file MUST NOT be created in dry-run
    assert not dest_audio.exists()

    # Returned metadata and calculated destination path should be correct
    assert meta.title == "Test Song"
    assert meta.artist == "Test Artist"
    assert "Test Artist" in str(dest_audio)


def test_dry_run_reorganize(tmp_path):
    library_dir = tmp_path / "Music"
    temp_dir = tmp_path / "temp"
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=library_dir, temp_dir=temp_dir),
    )
    pipeline = ProcessingPipeline(config)

    # Place a file in an incorrect folder
    wrong_dir = library_dir / "WrongArtist" / "WrongAlbum"
    wrong_dir.mkdir(parents=True, exist_ok=True)
    file_path = wrong_dir / "01 - Correct Title.opus"
    create_dummy_opus(file_path, title="Correct Title", artist="Actual Artist")

    # Run reorganize with dry_run=True
    moved = pipeline.reorganize_paths([file_path], dry_run=True)
    assert len(moved) == 1
    old_p, new_p = moved[0]

    assert old_p == file_path
    assert "Actual Artist" in str(new_p)

    # File MUST NOT have actually moved on disk
    assert file_path.exists()
    assert not new_p.exists()


def test_cli_dry_run_commands(tmp_path):
    runner = CliRunner()
    test_file = tmp_path / "01 - Sample.opus"
    create_dummy_opus(test_file, title="Sample Song", artist="Sample Artist")

    result = runner.invoke(app, ["process", str(test_file), "--dry-run"])
    assert result.exit_code == 0
    assert "DRY-RUN" in result.stdout
    assert test_file.exists()

    result_reorg = runner.invoke(app, ["reorganize", str(test_file), "--dry-run"])
    assert result_reorg.exit_code == 0
    assert "DRY-RUN" in result_reorg.stdout
    assert test_file.exists()
