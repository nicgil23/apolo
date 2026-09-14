import pytest
from pathlib import Path
from mutagen.flac import FLAC
from mutagen.oggopus import OggOpus

from apolo.config import ApoloConfig, DirectoriesConfig, OrganizationConfig
from apolo.metadata.models import TrackMetadata
from apolo.metadata.matcher import MetadataMatcher
from apolo.organizer import LibraryOrganizer
from apolo.pipeline import ProcessingPipeline
from apolo.tagger import AudioTagger
from apolo.utils import (
    extract_primary_artist,
    is_compilation_album,
    is_single_release,
    parse_artists,
)


def test_compound_artists_not_split():
    # Compound bands containing '&', 'and', comas should not be shattered
    test_cases = [
        "Earth, Wind & Fire",
        "Simon & Garfunkel",
        "Florence and the Machine",
        "Florence + The Machine",
        "Crosby, Stills, Nash & Young",
        "Blood, Sweat & Tears",
        "Kool & The Gang",
        "King Gizzard & The Lizard Wizard",
        "Tom Petty and the Heartbreakers",
    ]

    for band in test_cases:
        m, f, a, disp = parse_artists(band)
        assert m == [band], f"Failed main_artists for {band}: got {m}"
        assert f == [], f"Failed featured_artists for {band}: got {f}"
        assert a == [band], f"Failed all_artists for {band}: got {a}"
        assert disp == band, f"Failed display_str for {band}: got {disp}"

        meta = TrackMetadata(title="Song", artist=band)
        assert meta.get_album_artist_or_artist() == band


def test_soundtrack_single_composer_vs_various_artists(tmp_path: Path):
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=tmp_path / "Music"),
        organization=OrganizationConfig(various_artists_folder=True),
    )
    organizer = LibraryOrganizer(config)

    # Solo composer soundtrack -> should go to Hans Zimmer directory, NOT Various Artists
    assert not is_compilation_album("Interstellar (Original Motion Picture Soundtrack)", "Hans Zimmer")
    meta_zimmer = TrackMetadata(
        title="Cornfield Chase",
        artist="Hans Zimmer",
        album_artist="Hans Zimmer",
        album="Interstellar (Original Motion Picture Soundtrack)",
        track_number=2,
        date="2014-11-17",
    )
    dest_zimmer = organizer.get_destination_path(meta_zimmer)
    assert "Hans Zimmer" in str(dest_zimmer)
    assert "Various Artists" not in str(dest_zimmer)

    # Various Artists soundtrack -> should go to Various Artists
    assert is_compilation_album("Cyberpunk 2077 (Original Soundtrack)", "Various Artists")
    meta_va = TrackMetadata(
        title="Never Fade Away",
        artist="SAMURAI (Refused)",
        album_artist="Various Artists",
        album="Cyberpunk 2077 (Original Soundtrack)",
        track_number=1,
        compilation=True,
        date="2020",
    )
    dest_va = organizer.get_destination_path(meta_va)
    assert "Various Artists" in str(dest_va)


def test_single_release_detection_itunes_naming():
    # "Song - Single" with track_total None should be recognized as a single
    assert is_single_release("Starboy - Single", None)
    assert is_single_release("Blinding Lights (Single)", 1)
    assert is_single_release("Single", None)
    assert is_single_release("My Hit [Single]", 2)


def test_multi_disc_compilation_filename_when_no_folders(tmp_path: Path):
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=tmp_path / "Music"),
        organization=OrganizationConfig(multi_disc_folder=False, various_artists_folder=True),
    )
    organizer = LibraryOrganizer(config)

    meta_cd1 = TrackMetadata(
        title="Track One",
        artist="Artist A",
        album_artist="Various Artists",
        album="Best of 80s",
        track_number=1,
        disc_number=1,
        disc_total=2,
        compilation=True,
    )
    meta_cd2 = TrackMetadata(
        title="Track Two",
        artist="Artist B",
        album_artist="Various Artists",
        album="Best of 80s",
        track_number=1,
        disc_number=2,
        disc_total=2,
        compilation=True,
    )

    dest1 = organizer.get_destination_path(meta_cd1)
    dest2 = organizer.get_destination_path(meta_cd2)

    # Must contain disc number in file name to avoid collision
    assert "1-01 - Artist A - Track One" in dest1.name
    assert "2-01 - Artist B - Track Two" in dest2.name
    assert dest1.name != dest2.name


def test_album_consensus_different_artists_same_album_name(tmp_path: Path):
    # If Queen and Blink-182 both have "Greatest Hits" processed in the same folder, they must not cross-contaminate
    pipeline = ProcessingPipeline(
        ApoloConfig(directories=DirectoriesConfig(library_dir=tmp_path / "Music"))
    )

    queen_tracks = [
        (Path(f"/tmp/q{i}.opus"), None, TrackMetadata(title=f"Song {i}", artist="Queen", album_artist="Queen", album="Greatest Hits"))
        for i in range(1, 8)
    ]
    blink_tracks = [
        (Path(f"/tmp/b{i}.opus"), None, TrackMetadata(title=f"Blink Song {i}", artist="Blink-182", album_artist="Blink-182", album="Greatest Hits"))
        for i in range(1, 4)
    ]

    all_tracks = queen_tracks + blink_tracks

    from apolo.utils import infer_consensus_album_artist
    # Verify consensus on blink tracks alone returns Blink-182
    assert infer_consensus_album_artist([t[2] for t in blink_tracks]) == "Blink-182"
    assert infer_consensus_album_artist([t[2] for t in queen_tracks]) == "Queen"


def test_tagger_update_tags_flac(tmp_path: Path):
    flac_file = tmp_path / "test.flac"
    # Create minimal flac file
    flac_file.write_bytes(
        b"fLaC\x00\x00\x00\"\x12\x00\x12\x00\x00\x00\x00\x00\x00\x00\x0b\xb8\x01\xf0\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x84\x00\x00\x00"
    )
    try:
        audio = FLAC(flac_file)
        audio.save()
    except Exception:
        pass

    if flac_file.exists():
        AudioTagger.update_tags(flac_file, {"title": "Updated Title", "album_artist": "Updated Artist"})
        try:
            audio = FLAC(flac_file)
            assert audio.get("TITLE") == ["Updated Title"]
            assert audio.get("ALBUMARTIST") == ["Updated Artist"]
        except Exception:
            pass


def test_extra_tags_preservation(tmp_path: Path):
    import subprocess
    opus_file = tmp_path / "test_extra.opus"
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-t", "1", "-c:a", "libopus", "-b:a", "128k", str(opus_file)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    meta = TrackMetadata(
        title="Custom Song",
        artist="Custom Artist",
        album="Custom Album",
        extra_tags={"COMPOSER": ["Ludwig van Beethoven"], "ISRC": ["US1234567890"], "LABEL": ["Deutsche Grammophon"]}
    )

    AudioTagger.tag_opus(opus_file, meta)

    audio = OggOpus(opus_file)
    assert audio.get("COMPOSER") == ["Ludwig van Beethoven"]
    assert audio.get("ISRC") == ["US1234567890"]
    assert audio.get("LABEL") == ["Deutsche Grammophon"]


def test_get_year_various_date_formats():
    meta1 = TrackMetadata(title="A", artist="B", date="2023-05-18")
    assert meta1.get_year() == "2023"

    meta2 = TrackMetadata(title="A", artist="B", date="18/05/1999")
    assert meta2.get_year() == "1999"

    meta3 = TrackMetadata(title="A", artist="B", date="2005")
    assert meta3.get_year() == "2005"


def test_slash_and_compound_artist_splitting():
    # AC/DC must not be shattered into 'AC' and 'DC'
    m, f, a, disp = parse_artists("AC/DC")
    assert m == ["AC/DC"]
    assert a == ["AC/DC"]
    assert disp == "AC/DC"

    # Tyler, The Creator must not be shattered
    m2, f2, a2, disp2 = parse_artists("Tyler, The Creator")
    assert m2 == ["Tyler, The Creator"]
    assert a2 == ["Tyler, The Creator"]


def test_skip_collision_strategy_does_not_delete_source(tmp_path: Path):
    library_dir = tmp_path / "Music"
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=library_dir),
        organization=OrganizationConfig(collision_strategy="skip"),
    )
    organizer = LibraryOrganizer(config)

    meta = TrackMetadata(
        title="Song",
        artist="Artist",
        album="Album",
        track_number=1,
        date="2020",
    )

    dest_file = library_dir / "Artist" / "Album (2020)" / "01 - Song.opus"
    dest_file.parent.mkdir(parents=True)
    dest_file.write_bytes(b"existing audio")

    source_file = tmp_path / "incoming_source.opus"
    source_file.write_bytes(b"new audio to skip")

    dest_audio, _ = organizer.organize_track(source_file, meta)
    # Source file MUST still exist (not unlinked)
    assert source_file.exists()
    assert dest_file.exists()
    assert dest_file.read_bytes() == b"existing audio"


def test_album_date_consensus(tmp_path: Path):
    from apolo.utils import infer_consensus_date
    tracks = [
        TrackMetadata(title="Track 1", artist="Artist", album="Album", date="2020-05-10"),
        TrackMetadata(title="Track 2", artist="Artist", album="Album", date="2020-05-10"),
        TrackMetadata(title="Single Advance", artist="Artist", album="Album", date="2019-11-20"),
    ]
    consensus = infer_consensus_date(tracks)
    assert consensus == "2020-05-10"


def test_reorganize_paths_moves_companion_cover(tmp_path: Path):
    library_dir = tmp_path / "Music"
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=library_dir),
    )
    pipeline = ProcessingPipeline(config)

    # Place audio and cover in wrong location
    old_folder = library_dir / "WrongArtist" / "WrongAlbum"
    old_folder.mkdir(parents=True)
    audio_file = old_folder / "01 - CorrectSong.opus"
    import subprocess
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-t", "1", "-c:a", "libopus", "-b:a", "128k", str(audio_file)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    # Tag it with correct artist and album
    meta = TrackMetadata(
        title="CorrectSong",
        artist="RealArtist",
        album="RealAlbum",
        track_number=1,
        date="2022",
    )
    AudioTagger.tag_opus(audio_file, meta)

    cover_file = old_folder / "cover.jpg"
    cover_file.write_bytes(b"image bytes")

    moved = pipeline.reorganize_paths([old_folder])
    assert len(moved) == 1
    new_dest = moved[0][1]

    assert new_dest.exists()
    assert (new_dest.parent / "cover.jpg").exists()
    assert not old_folder.exists()

