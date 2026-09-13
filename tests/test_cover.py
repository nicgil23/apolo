import io
import subprocess
from pathlib import Path
from PIL import Image
import pytest
from mutagen.oggopus import OggOpus
from typer.testing import CliRunner

from apolo.cli import app
from apolo.cover import CoverManager
from apolo.metadata.models import TrackMetadata
from apolo.tagger import AudioTagger


def create_dummy_opus_with_cover(output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
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

    img = Image.new("RGB", (400, 400), color="green")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")

    meta = TrackMetadata(title="Cover Song", artist="Cover Artist", cover_art_data=buf.getvalue())
    AudioTagger.tag_opus(output_path, meta)


def test_cover_extract(tmp_path):
    album_dir = tmp_path / "Artist" / "Album"
    opus_file = album_dir / "01 - Song.opus"
    create_dummy_opus_with_cover(opus_file)

    extracted = CoverManager.extract_covers([album_dir], target_filename="cover.jpg")
    assert len(extracted) == 1
    src, cover_out = extracted[0]
    assert cover_out.exists()
    assert cover_out.name == "cover.jpg"
    assert cover_out.parent == album_dir


def test_cover_set(tmp_path):
    album_dir = tmp_path / "Artist" / "Album"
    opus_file = album_dir / "01 - Song.opus"
    create_dummy_opus_with_cover(opus_file)

    # Create new cover image
    new_cover_path = tmp_path / "new_cover.png"
    img = Image.new("RGB", (800, 800), color="red")
    img.save(new_cover_path)

    updated = CoverManager.set_album_cover([album_dir], new_cover_path)
    assert updated == 1

    audio = OggOpus(opus_file)
    assert "METADATA_BLOCK_PICTURE" in audio


def test_cover_cli_command(tmp_path):
    runner = CliRunner()
    album_dir = tmp_path / "Artist" / "Album"
    opus_file = album_dir / "01 - Track.opus"
    create_dummy_opus_with_cover(opus_file)

    res = runner.invoke(app, ["cover", "extract", str(album_dir)])
    assert res.exit_code == 0
    assert "Extracted Cover Art" in res.stdout
    assert (album_dir / "cover.jpg").exists()
