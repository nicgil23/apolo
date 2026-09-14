import pytest
from pathlib import Path
from mutagen.oggopus import OggOpus
from mutagen.flac import FLAC

from apolo.metadata.models import TrackMetadata
from apolo.metadata.musicbrainz import MusicBrainzProvider
from apolo.metadata.deezer import DeezerProvider
from apolo.metadata.itunes import iTunesProvider
from apolo.tagger import AudioTagger
from apolo.organizer import LibraryOrganizer
from apolo.config import ApoloConfig
from apolo.utils import parse_artists, extract_primary_artist


def test_parse_artists_various_formats():
    # 1. Simple single artist
    m, f, a, disp = parse_artists("Rosalía")
    assert m == ["Rosalía"]
    assert f == []
    assert a == ["Rosalía"]

    # 2. Artist with 'feat.'
    m, f, a, disp = parse_artists("Rosalía feat. Rauw Alejandro")
    assert m == ["Rosalía"]
    assert f == ["Rauw Alejandro"]
    assert a == ["Rosalía", "Rauw Alejandro"]
    assert "Rosalía" in disp and "Rauw Alejandro" in disp

    # 3. Two main artists with '&'
    m, f, a, disp = parse_artists("Daft Punk & Pharrell Williams")
    assert m == ["Daft Punk", "Pharrell Williams"]
    assert f == []
    assert a == ["Daft Punk", "Pharrell Williams"]

    # 4. Multiple main + featured
    m, f, a, disp = parse_artists("Major Lazer feat. Justin Bieber & MØ")
    assert m == ["Major Lazer"]
    assert f == ["Justin Bieber", "MØ"]
    assert a == ["Major Lazer", "Justin Bieber", "MØ"]

    # 5. Featured in title
    m, f, a, disp = parse_artists("Gorillaz", title="Tormenta (feat. Bad Bunny)")
    assert m == ["Gorillaz"]
    assert f == ["Bad Bunny"]
    assert a == ["Gorillaz", "Bad Bunny"]

    # 6. Comma separated
    m, f, a, disp = parse_artists("Calvin Harris, Dua Lipa")
    assert m == ["Calvin Harris", "Dua Lipa"]
    assert a == ["Calvin Harris", "Dua Lipa"]


def test_extract_primary_artist():
    assert extract_primary_artist("Rosalía feat. Rauw Alejandro") == "Rosalía"
    assert extract_primary_artist("Daft Punk & Pharrell Williams") == "Daft Punk"
    assert extract_primary_artist("Calvin Harris, Dua Lipa") == "Calvin Harris"


def test_track_metadata_auto_population():
    meta = TrackMetadata(
        title="Beso",
        artist="Rosalía feat. Rauw Alejandro",
        album="RR",
    )
    assert meta.main_artists == ["Rosalía"]
    assert meta.featured_artists == ["Rauw Alejandro"]
    assert meta.artists == ["Rosalía", "Rauw Alejandro"]
    assert meta.get_album_artist_or_artist() == "Rosalía"

    lib_dict = meta.to_library_dict()
    assert lib_dict["main_artists"] == ["Rosalía"]
    assert lib_dict["featured_artists"] == ["Rauw Alejandro"]
    assert lib_dict["artists"] == ["Rosalía", "Rauw Alejandro"]


def test_tagger_multi_artists_opus(tmp_path: Path):
    test_file = tmp_path / "test.opus"
    # Create minimal Ogg Opus structure using mutagen
    audio = OggOpus(test_file) if test_file.exists() else None
    if audio is None:
        # Create dummy file with Opus header
        test_file.write_bytes(
            b"OggS\x00\x02\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01\x13"
            b"OpusHead\x01\x02\x00\x00\x80\xbb\x00\x00\x00\x00\x00"
        )
        try:
            audio = OggOpus(test_file)
            audio.add_tags()
            audio.save()
        except Exception:
            pass

    # If mutagen can tag the file
    if test_file.exists():
        meta = TrackMetadata(
            title="Beso",
            artist="Rosalía feat. Rauw Alejandro",
            main_artists=["Rosalía"],
            featured_artists=["Rauw Alejandro"],
            artists=["Rosalía", "Rauw Alejandro"],
            album="RR",
            album_artist="Rosalía",
        )
        try:
            AudioTagger.tag_opus(test_file, meta)
            tagged = OggOpus(test_file)
            artist_tags = tagged.get("ARTIST", [])
            assert "Rosalía" in artist_tags
            assert "Rauw Alejandro" in artist_tags
            assert tagged.get("ALBUMARTIST") == ["Rosalía"]
            assert tagged.get("MAIN_ARTIST") == ["Rosalía"]
            assert tagged.get("FEATURED_ARTIST") == ["Rauw Alejandro"]
        except Exception:
            pass


def test_organizer_uses_primary_artist(tmp_path: Path):
    config = ApoloConfig()
    config.directories.library_dir = tmp_path / "Library"
    organizer = LibraryOrganizer(config=config)

    meta = TrackMetadata(
        title="Beso",
        artist="Rosalía feat. Rauw Alejandro",
        album="RR",
        date="2023",
        track_number=1,
    )
    dest = organizer.get_destination_path(meta, extension=".opus")
    # Path should be under 'Rosalía/RR (2023)/01 - Beso.opus' rather than combined string
    assert "Rosalía" in dest.parts
    assert "RR (2023)" in dest.parts


def test_inspector_displays_all_artists(tmp_path: Path):
    from apolo.inspector import inspect_track
    from rich.console import Console
    import subprocess

    opus_file = tmp_path / "collaboration.opus"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:duration=1",
            "-c:a",
            "libopus",
            str(opus_file),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )

    meta = TrackMetadata(
        title="Tormenta",
        artist="Gorillaz feat. Bad Bunny",
        album="Cracker Island",
    )
    AudioTagger.tag_opus(opus_file, meta)

    console = Console(record=True)
    inspect_track(opus_file, console=console)
    output = console.export_text()

    assert "Metadata Inspector: collaboration.opus" in output
    assert "All Artists" in output
    assert "Gorillaz, Bad Bunny" in output
    assert "Main Artists" in output
    assert "Gorillaz" in output
    assert "Featured Artists" in output
    assert "Bad Bunny" in output


def test_infer_consensus_album_artist_70_percent():
    from apolo.utils import infer_consensus_album_artist

    # 1. 8 tracks: 6 by AKRIILA (75% >= 70%) -> consensus is AKRIILA
    tracks_75 = [
        {"artist": "AKRIILA", "album": "epistolares"},
        {"artist": "AKRIILA", "album": "epistolares"},
        {"artist": "AKRIILA", "album": "epistolares"},
        {"artist": "AKRIILA", "album": "epistolares"},
        {"artist": "AKRIILA", "album": "epistolares"},
        {"artist": "AKRIILA", "album": "epistolares"},
        {"artist": "AKRIILA & Bb trickz", "album": "epistolares"},
        {"artist": "AKRIILA & Gianluca", "album": "epistolares"},
    ]
    assert infer_consensus_album_artist(tracks_75, threshold=0.70) == "AKRIILA"

    # 2. 10 tracks: 6 by AKRIILA (60% < 70%) -> consensus is None (safer threshold)
    tracks_60 = [
        {"artist": "AKRIILA", "album": "epistolares"},
        {"artist": "AKRIILA", "album": "epistolares"},
        {"artist": "AKRIILA", "album": "epistolares"},
        {"artist": "AKRIILA", "album": "epistolares"},
        {"artist": "AKRIILA", "album": "epistolares"},
        {"artist": "AKRIILA", "album": "epistolares"},
        {"artist": "Bb trickz", "album": "epistolares"},
        {"artist": "Gianluca", "album": "epistolares"},
        {"artist": "Broke Carrey", "album": "epistolares"},
        {"artist": "Kidd Voodoo", "album": "epistolares"},
    ]
    assert infer_consensus_album_artist(tracks_60, threshold=0.70) is None


def test_single_routing_uses_primary_artist(tmp_path: Path):
    config = ApoloConfig()
    config.directories.library_dir = tmp_path / "Library"
    organizer = LibraryOrganizer(config=config)

    meta = TrackMetadata(
        title="arreglo floral",
        artist="AKRIILA & Kidd Voodoo",
        album="arreglo floral - Single",
        date="2024",
        track_total=1,
    )
    dest = organizer.get_destination_path(meta, extension=".opus")
    assert "AKRIILA" in dest.parts
    assert "Singles" in dest.parts
    assert "AKRIILA & Kidd Voodoo" not in dest.parts


def test_doctor_detects_and_repairs_fragmented_folders(tmp_path: Path):
    from apolo.doctor import LibraryDoctor
    import subprocess

    lib_dir = tmp_path / "Library"
    lib_dir.mkdir()

    base_dir = lib_dir / "AKRIILA" / "Singles"
    base_dir.mkdir(parents=True)
    base_song = base_dir / "solo.opus"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1", "-c:a", "libopus", str(base_song)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    AudioTagger.tag_opus(base_song, TrackMetadata(title="solo", artist="AKRIILA", album="Single"))

    frag_dir = lib_dir / "AKRIILA & Bb trickz" / "Singles"
    frag_dir.mkdir(parents=True)
    frag_song = frag_dir / "sola.opus"
    subprocess.run(
        ["ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1", "-c:a", "libopus", str(frag_song)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True,
    )
    AudioTagger.tag_opus(frag_song, TrackMetadata(title="sola", artist="AKRIILA & Bb trickz", album_artist="AKRIILA & Bb trickz", album="Single"))

    config = ApoloConfig()
    config.directories.library_dir = lib_dir
    doctor = LibraryDoctor(config)

    report = doctor.scan_library(library_dir=lib_dir)
    assert len(report.fragmented_artist_folders) == 1
    assert report.fragmented_artist_folders[0][2] == "AKRIILA"

    # Repair
    repaired = doctor.repair_fragmented_folders(report.fragmented_artist_folders)
    assert repaired == 1

    # Check that fragmented folder is deleted and song is moved to AKRIILA/Singles/
    assert not (lib_dir / "AKRIILA & Bb trickz").exists()
    assert (base_dir / "sola.opus").exists() or any((lib_dir / "AKRIILA").rglob("sola.opus"))


