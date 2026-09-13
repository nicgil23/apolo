import io
import subprocess
from pathlib import Path
from PIL import Image
import pytest
from mutagen.oggopus import OggOpus
from typer.testing import CliRunner

from apolo.cli import app
from apolo.config import ApoloConfig, DirectoriesConfig
from apolo.metadata.models import TrackMetadata
from apolo.tagger import AudioTagger


def create_dummy_opus(output_path: Path, title: str = "Original Title", artist: str = "Original Artist"):
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
        album="Original Album",
        date="2020",
        track_number=1,
        genre="Rock",
    )
    AudioTagger.tag_opus(output_path, meta)


def test_tagger_update_tags_partial(tmp_path):
    opus_file = tmp_path / "track.opus"
    create_dummy_opus(opus_file)

    # Update only genre and date
    AudioTagger.update_tags(opus_file, {"genre": "Synthwave", "date": "2024"})

    audio = OggOpus(opus_file)
    # Changed fields
    assert audio["GENRE"] == ["Synthwave"]
    assert audio["DATE"] == ["2024"]
    # Preserved fields
    assert audio["TITLE"] == ["Original Title"]
    assert audio["ARTIST"] == ["Original Artist"]
    assert audio["ALBUM"] == ["Original Album"]


def test_tagger_update_cover(tmp_path):
    opus_file = tmp_path / "track_cover.opus"
    create_dummy_opus(opus_file)

    img = Image.new("RGB", (100, 100), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    cover_bytes = buf.getvalue()

    AudioTagger.update_tags(opus_file, {}, cover_data=cover_bytes)

    audio = OggOpus(opus_file)
    assert "METADATA_BLOCK_PICTURE" in audio


def test_cli_set_command(tmp_path):
    runner = CliRunner()
    opus_file = tmp_path / "test_set.opus"
    create_dummy_opus(opus_file)

    # Update title and year via CLI
    result = runner.invoke(app, [
        "set",
        str(opus_file),
        "--title", "New Shiny Title",
        "--year", "2025",
        "--genre", "Electronic",
    ])
    assert result.exit_code == 0
    assert "New Shiny Title" in result.stdout

    audio = OggOpus(opus_file)
    assert audio["TITLE"] == ["New Shiny Title"]
    assert audio["DATE"] == ["2025"]
    assert audio["GENRE"] == ["Electronic"]
    # Preserved
    assert audio["ARTIST"] == ["Original Artist"]


def test_cli_set_dry_run(tmp_path):
    runner = CliRunner()
    opus_file = tmp_path / "test_set_dry.opus"
    create_dummy_opus(opus_file, title="Untouched Title")

    result = runner.invoke(app, [
        "set",
        str(opus_file),
        "--title", "Modified Title",
        "--dry-run",
    ])
    assert result.exit_code == 0
    assert "DRY-RUN" in result.stdout

    audio = OggOpus(opus_file)
    assert audio["TITLE"] == ["Untouched Title"]


def test_cli_edit_replace_and_regex(tmp_path):
    runner = CliRunner()
    opus_file = tmp_path / "test_edit.opus"
    create_dummy_opus(opus_file, title="Song Name (Official Video) [Remastered]")

    # Use regex to clean video and remaster tags
    result = runner.invoke(app, [
        "edit",
        str(opus_file),
        "--regex-title", r"\s*[\(\[][^)\]]*(Official|Remastered)[^)\]]*[\)\]]", "",
    ])
    assert result.exit_code == 0

    audio = OggOpus(opus_file)
    assert audio["TITLE"] == ["Song Name"]


def test_cli_edit_dry_run(tmp_path):
    runner = CliRunner()
    opus_file = tmp_path / "test_edit_dry.opus"
    create_dummy_opus(opus_file, title="Old Title")

    result = runner.invoke(app, [
        "edit",
        str(opus_file),
        "--replace-title", "Old", "New",
        "--dry-run",
    ])
    assert result.exit_code == 0
    assert "DRY-RUN" in result.stdout

    audio = OggOpus(opus_file)
    assert audio["TITLE"] == ["Old Title"]
