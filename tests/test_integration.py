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


def test_inbox_preserves_sidecar_lrc(tmp_path):
    inbox_dir = tmp_path / "Inbox"
    library_dir = tmp_path / "Library"
    temp_dir = tmp_path / "temp"
    for d in [inbox_dir, library_dir, temp_dir]:
        d.mkdir(parents=True, exist_ok=True)

    config = ApoloConfig(
        directories=DirectoriesConfig(inbox_dir=inbox_dir, library_dir=library_dir, temp_dir=temp_dir)
    )
    pipeline = ProcessingPipeline(config)

    album_dir = inbox_dir / "Ameri"
    album_dir.mkdir()
    track = album_dir / "10. Duki - Barro.opus"
    create_dummy_opus(track)

    custom_lrc_content = "[00:10.00] Mi letra personalizada anterior\n[00:15.00] Otra linea"
    sidecar_lrc = album_dir / "10. Duki - Barro.lrc"
    sidecar_lrc.write_text(custom_lrc_content, encoding="utf-8")

    results = pipeline.process_directory(inbox_dir)
    assert len(results) == 1
    dest_audio, dest_lrc, meta = results[0]

    assert dest_audio.exists()
    assert dest_lrc is not None and dest_lrc.exists()
    assert dest_lrc.read_text(encoding="utf-8") == custom_lrc_content

    # Check that source sidecar lrc was removed and inbox is clean
    assert not sidecar_lrc.exists()
    assert not album_dir.exists()


def test_inbox_embeds_and_cleans_folder_images(tmp_path):
    inbox_dir = tmp_path / "Inbox"
    library_dir = tmp_path / "Library"
    temp_dir = tmp_path / "temp"
    for d in [inbox_dir, library_dir, temp_dir]:
        d.mkdir(parents=True, exist_ok=True)

    config = ApoloConfig(
        directories=DirectoriesConfig(inbox_dir=inbox_dir, library_dir=library_dir, temp_dir=temp_dir)
    )
    pipeline = ProcessingPipeline(config)

    album_dir = inbox_dir / "Ameri"
    album_dir.mkdir()
    track1 = album_dir / "01. Duki - Track1.opus"
    track2 = album_dir / "02. Duki - Track2.opus"
    create_dummy_opus(track1)
    create_dummy_opus(track2)

    cover_file = album_dir / "cover.jpg"
    cover_file.write_bytes(create_dummy_cover_bytes())

    results = pipeline.process_directory(inbox_dir)
    assert len(results) == 2

    for dest_audio, dest_lrc, meta in results:
        assert dest_audio.exists()
        # Verify cover was embedded
        embedded_cover = AudioTagger.extract_cover_art_from_file(dest_audio)
        assert embedded_cover is not None and len(embedded_cover) > 0

    # Verify cover file was deleted and folder was removed
    assert not cover_file.exists()
    assert not album_dir.exists()

