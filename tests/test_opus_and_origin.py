import io
import subprocess
from pathlib import Path
from PIL import Image
import pytest
from mutagen.oggopus import OggOpus
from mutagen.flac import FLAC, Picture as FLACPicture

from apolo.config import ApoloConfig, DirectoriesConfig, DownloaderConfig
from apolo.metadata.models import TrackMetadata
from apolo.pipeline import ProcessingPipeline, is_well_tagged
from apolo.tagger import AudioTagger


def create_dummy_flac(output_path: Path, add_cover: bool = True):
    """Generates a 1-second silence FLAC file with native metadata."""
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=44100:cl=stereo",
        "-t",
        "1",
        "-c:a",
        "flac",
        str(output_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    audio = FLAC(output_path)
    audio["TITLE"] = ["My Soulseek Song"]
    audio["ARTIST"] = ["Rare Underground Artist"]
    audio["ALBUM"] = ["Underground Gems LP"]
    audio["ALBUMARTIST"] = ["Rare Underground Artist"]
    audio["TRACKNUMBER"] = ["04"]
    audio["TRACKTOTAL"] = ["12"]
    audio["DATE"] = ["2019-10-31"]
    audio["GENRE"] = ["Dark Ambient"]

    if add_cover:
        img = Image.new("RGB", (200, 200), color="red")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        pic = FLACPicture()
        pic.data = buf.getvalue()
        pic.type = 3
        pic.mime = "image/jpeg"
        pic.width, pic.height = 200, 200
        pic.depth = 24
        audio.add_picture(pic)

    audio.save()


def create_dummy_mp4_video(output_path: Path):
    """Generates a 1-second dummy MP4 video with audio."""
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=1:size=320x240:rate=1",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=44100:cl=stereo",
        "-t",
        "1",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def test_is_well_tagged():
    # Incomplete / missing native tags
    assert not is_well_tagged({"has_native_tags": False, "title": "Song", "artist": "Artist"})
    assert not is_well_tagged({"has_native_tags": True, "title": "", "artist": "Artist"})
    assert not is_well_tagged({"has_native_tags": True, "title": "Song", "artist": "Unknown Artist"})

    # Well tagged with album and track number
    assert is_well_tagged({
        "has_native_tags": True,
        "title": "Solar Wind",
        "artist": "Stellar",
        "album": "Cosmos",
        "track_number": 2,
    })

    # Well tagged with date and track number
    assert is_well_tagged({
        "has_native_tags": True,
        "title": "Solar Wind",
        "artist": "Stellar",
        "track_number": 2,
        "date": "2022",
    })


def test_flac_transcoding_and_metadata_preservation(tmp_path):
    library_dir = tmp_path / "Music"
    temp_dir = tmp_path / "temp"
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=library_dir, temp_dir=temp_dir),
        downloader=DownloaderConfig(audio_bitrate="256k", default_origin="local", preserve_existing_tags=True),
    )
    pipeline = ProcessingPipeline(config)

    flac_file = tmp_path / "04 - My Soulseek Song.flac"
    create_dummy_flac(flac_file, add_cover=True)

    res = pipeline.process_file(flac_file, origin="soulseek")
    assert res is not None
    dest_audio, dest_lrc, meta = res

    # Check that output is .opus
    assert dest_audio.exists()
    assert dest_audio.suffix == ".opus"

    # Verify original metadata was preserved and not overridden
    assert meta.title == "My Soulseek Song"
    assert meta.artist == "Rare Underground Artist"
    assert meta.album == "Underground Gems LP"
    assert meta.track_number == 4
    assert meta.track_total == 12
    assert meta.date == "2019-10-31"
    assert meta.genre == "Dark Ambient"
    assert meta.origin == "soulseek"
    assert meta.provider_source == "existing_metadata"

    # Check tags inside Opus file
    opus_tags = OggOpus(dest_audio)
    assert opus_tags["TITLE"] == ["My Soulseek Song"]
    assert opus_tags["ARTIST"] == ["Rare Underground Artist"]
    assert opus_tags["ALBUM"] == ["Underground Gems LP"]
    assert opus_tags["ORIGIN"] == ["soulseek"]
    assert opus_tags["SOURCE"] == ["soulseek"]
    assert opus_tags["ORIGEN"] == ["soulseek"]
    assert "METADATA_BLOCK_PICTURE" in opus_tags

    # Verify original flac was cleaned up after successful transcoding
    assert not flac_file.exists()


def test_video_transcoding_to_opus(tmp_path):
    library_dir = tmp_path / "Music"
    temp_dir = tmp_path / "temp"
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=library_dir, temp_dir=temp_dir),
    )
    pipeline = ProcessingPipeline(config)

    mp4_file = tmp_path / "Daft Punk - Get Lucky.mp4"
    create_dummy_mp4_video(mp4_file)

    res = pipeline.process_file(mp4_file, origin="youtube_rip")
    assert res is not None
    dest_audio, dest_lrc, meta = res

    assert dest_audio.exists()
    assert dest_audio.suffix == ".opus"
    assert meta.origin == "youtube_rip"

    opus_tags = OggOpus(dest_audio)
    assert opus_tags["ORIGIN"] == ["youtube_rip"]
