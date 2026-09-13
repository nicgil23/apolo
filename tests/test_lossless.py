import subprocess
from pathlib import Path
import mutagen
from mutagen.flac import FLAC, Picture
import pytest

from apolo.config import ApoloConfig, DirectoriesConfig, DownloaderConfig
from apolo.metadata.models import TrackMetadata
from apolo.organizer import LibraryOrganizer
from apolo.pipeline import ProcessingPipeline
from apolo.tagger import AudioTagger


def create_dummy_flac(path: Path):
    """Creates a real valid FLAC audio file using ffmpeg."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:a",
            "flac",
            str(path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )


def test_tag_flac_metadata(tmp_path: Path):
    flac_file = tmp_path / "test.flac"
    create_dummy_flac(flac_file)

    meta = TrackMetadata(
        title="Lossless Song",
        artist="Lossless Artist",
        album="Audiophile Album",
        track_number=1,
        track_total=10,
        disc_number=1,
        disc_total=1,
        date="2024",
        genre="Jazz",
        origin="bandcamp_flac",
        synced_lyrics="[00:01.00]Hi-Fi audio lyric",
    )

    tagger = AudioTagger()
    tagger.tag_flac(flac_file, meta)

    audio = FLAC(str(flac_file))
    assert audio["TITLE"] == ["Lossless Song"]
    assert audio["ARTIST"] == ["Lossless Artist"]
    assert audio["ALBUM"] == ["Audiophile Album"]
    assert audio["TRACKNUMBER"] == ["1"]
    assert audio["DATE"] == ["2024"]
    assert audio["ORIGIN"] == ["bandcamp_flac"]
    assert audio["LYRICS"] == ["[00:01.00]Hi-Fi audio lyric"]


def test_process_flac_with_preserve_lossless(tmp_path: Path, monkeypatch):
    library_dir = tmp_path / "music"
    inbox_dir = tmp_path / "inbox"
    temp_dir = tmp_path / "temp"
    for d in [library_dir, inbox_dir, temp_dir]:
        d.mkdir(parents=True)

    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=library_dir, inbox_dir=inbox_dir, temp_dir=temp_dir),
        downloader=DownloaderConfig(preserve_lossless=True),
    )

    flac_file = inbox_dir / "flac_track.flac"
    create_dummy_flac(flac_file)

    pipeline = ProcessingPipeline(config)
    # Mock matcher to return quick metadata
    monkeypatch.setattr(
        pipeline.matcher,
        "find_best_match",
        lambda *args, **kwargs: TrackMetadata(
            title="Pristine Wave",
            artist="Sound Master",
            album="Master Tape",
            date="2023",
        ),
    )
    monkeypatch.setattr(pipeline.lyrics_provider, "get_synced_lyrics", lambda *args, **kwargs: None)

    res = pipeline.process_file(flac_file, preserve_lossless=True)
    assert res is not None
    dest_audio, _, meta = res

    assert dest_audio.suffix == ".flac"
    assert dest_audio.exists()
    assert not flac_file.exists()
    assert "Sound Master/Master Tape (2023)" in str(dest_audio)

    # Verify FLAC tags are intact
    audio = FLAC(str(dest_audio))
    assert audio["TITLE"] == ["Pristine Wave"]
    assert audio["ARTIST"] == ["Sound Master"]


def test_process_flac_without_preserve_lossless(tmp_path: Path, monkeypatch):
    library_dir = tmp_path / "music"
    inbox_dir = tmp_path / "inbox"
    temp_dir = tmp_path / "temp"
    for d in [library_dir, inbox_dir, temp_dir]:
        d.mkdir(parents=True)

    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=library_dir, inbox_dir=inbox_dir, temp_dir=temp_dir),
        downloader=DownloaderConfig(preserve_lossless=False),
    )

    flac_file = inbox_dir / "flac_track2.flac"
    create_dummy_flac(flac_file)

    pipeline = ProcessingPipeline(config)
    monkeypatch.setattr(
        pipeline.matcher,
        "find_best_match",
        lambda *args, **kwargs: TrackMetadata(
            title="Converted Song",
            artist="Artist X",
            album="Album Y",
            date="2022",
        ),
    )
    monkeypatch.setattr(pipeline.lyrics_provider, "get_synced_lyrics", lambda *args, **kwargs: None)

    res = pipeline.process_file(flac_file, preserve_lossless=False)
    assert res is not None
    dest_audio, _, meta = res

    # Should have converted to .opus
    assert dest_audio.suffix == ".opus"
    assert dest_audio.exists()


def test_reorganize_paths_preserves_flac_extension(tmp_path: Path):
    library_dir = tmp_path / "music"
    library_dir.mkdir(parents=True)

    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=library_dir, inbox_dir=tmp_path / "inbox", temp_dir=tmp_path / "temp"),
    )

    # Place a FLAC file in wrong directory
    wrong_dir = library_dir / "Misc"
    wrong_dir.mkdir()
    flac_file = wrong_dir / "track.flac"
    create_dummy_flac(flac_file)

    meta = TrackMetadata(
        title="Symphony 5",
        artist="Beethoven",
        album="Classics",
        date="1808",
        track_number=1,
    )
    tagger = AudioTagger()
    tagger.tag_flac(flac_file, meta)

    pipeline = ProcessingPipeline(config)
    moved = pipeline.reorganize_paths([wrong_dir])

    assert len(moved) == 1
    old_p, new_p = moved[0]
    assert new_p.suffix == ".flac"
    assert new_p.exists()
    assert "Beethoven/Classics (1808)/01 - Symphony 5.flac" in str(new_p)
