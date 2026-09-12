import os
import subprocess
import tempfile
from pathlib import Path
from PIL import Image
import pytest
from mutagen.oggopus import OggOpus

from apolo.config import ApoloConfig, DirectoriesConfig
from apolo.metadata.models import METADATOS_BIBLIOTECA, TrackMetadata
from apolo.organizer import LibraryOrganizer
from apolo.pipeline import ProcessingPipeline
from apolo.tagger import AudioTagger


def create_dummy_opus(output_path: Path):
    """Generates a 1-second silence opus file using ffmpeg."""
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
        str(output_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def create_dummy_cover_bytes() -> bytes:
    img = Image.new("RGB", (300, 300), color="blue")
    import io
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_tagging_and_reading_metadata(tmp_path):
    opus_path = tmp_path / "test.opus"
    create_dummy_opus(opus_path)

    cover_bytes = create_dummy_cover_bytes()
    meta = TrackMetadata(
        title="Test Song",
        artist="Test Artist",
        album_artist="Test Album Artist",
        album="Test Album",
        track_number=3,
        track_total=10,
        date="2024-01-15",
        genre="Synthwave",
        disc_number=1,
        disc_total=1,
        compilation=False,
        cover_art_data=cover_bytes,
        synced_lyrics="[00:00.50] Hello world\n[00:01.00] End test",
    )

    AudioTagger.tag_opus(opus_path, meta)

    # Verify tags with Mutagen
    audio = OggOpus(opus_path)
    assert audio["TITLE"] == ["Test Song"]
    assert audio["ARTIST"] == ["Test Artist"]
    assert audio["ALBUMARTIST"] == ["Test Album Artist"]
    assert audio["ALBUM"] == ["Test Album"]
    assert audio["TRACKNUMBER"] == ["3"]
    assert audio["TRACKTOTAL"] == ["10"]
    assert audio["DATE"] == ["2024-01-15"]
    assert audio["GENRE"] == ["Synthwave"]
    assert audio["DISCNUMBER"] == ["1"]
    assert audio["DISCTOTAL"] == ["1"]
    assert audio["COMPILATION"] == ["0"]
    assert "METADATA_BLOCK_PICTURE" in audio
    assert "[00:00.50] Hello world" in audio["LYRICS"][0]


def test_process_file_pipeline(tmp_path):
    library_dir = tmp_path / "Music"
    temp_dir = tmp_path / "temp"
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=library_dir, temp_dir=temp_dir)
    )
    pipeline = ProcessingPipeline(config)

    input_opus = tmp_path / "Daft Punk - Get Lucky.opus"
    create_dummy_opus(input_opus)

    res = pipeline.process_file(input_opus)
    assert res is not None
    dest_audio, dest_lrc, meta = res

    assert dest_audio.exists()
    assert "Daft Punk" in str(dest_audio)
    assert "Get Lucky" in str(dest_audio)
    assert dest_audio.suffix == ".opus"
