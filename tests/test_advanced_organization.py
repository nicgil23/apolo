import pytest
from pathlib import Path

from apolo.config import ApoloConfig, DirectoriesConfig, OrganizationConfig
from apolo.metadata.models import TrackMetadata
from apolo.organizer import LibraryOrganizer
from apolo.pipeline import ProcessingPipeline
from apolo.utils import (
    extract_disc_info,
    is_compilation_album,
    is_single_release,
    sanitize_filename,
)


def test_multi_disc_organization(tmp_path):
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=tmp_path / "Music"),
        organization=OrganizationConfig(multi_disc_folder=True),
    )
    organizer = LibraryOrganizer(config)

    meta_disc1 = TrackMetadata(
        title="In the Flesh?",
        artist="Pink Floyd",
        album_artist="Pink Floyd",
        album="The Wall",
        track_number=1,
        disc_number=1,
        disc_total=2,
        date="1979-11-30",
    )
    meta_disc2 = TrackMetadata(
        title="Hey You",
        artist="Pink Floyd",
        album_artist="Pink Floyd",
        album="The Wall",
        track_number=1,
        disc_number=2,
        disc_total=2,
        date="1979-11-30",
    )

    dest1 = organizer.get_destination_path(meta_disc1)
    dest2 = organizer.get_destination_path(meta_disc2)

    assert "Disc 01" in str(dest1)
    assert "Disc 02" in str(dest2)
    assert dest1.name == "01 - In the Flesh.opus"
    assert dest2.name == "01 - Hey You.opus"
    assert dest1 != dest2


def test_compilation_soundtrack_organization(tmp_path):
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=tmp_path / "Music"),
        organization=OrganizationConfig(various_artists_folder=True),
    )
    organizer = LibraryOrganizer(config)

    meta_ost = TrackMetadata(
        title="Never Fade Away",
        artist="SAMURAI (Refused)",
        album_artist="Various Artists",
        album="Cyberpunk 2077: Radio, Vol. 2 (Original Soundtrack)",
        track_number=3,
        compilation=True,
        date="2020-12-10",
    )

    dest = organizer.get_destination_path(meta_ost)
    assert "Various Artists" in str(dest)
    assert dest.name == "03 - SAMURAI (Refused) - Never Fade Away.opus"


def test_singles_organization(tmp_path):
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=tmp_path / "Music"),
        organization=OrganizationConfig(group_singles=True),
    )
    organizer = LibraryOrganizer(config)

    meta_single = TrackMetadata(
        title="Starboy",
        artist="The Weeknd",
        album="Single",
        track_number=1,
        date="2016-09-22",
    )

    dest = organizer.get_destination_path(meta_single)
    assert "The Weeknd" in str(dest)
    assert "Singles" in str(dest)
    assert dest.name == "Starboy (2016).opus"


def test_filename_length_truncation():
    super_long_title = "A" * 300
    sanitized = sanitize_filename(super_long_title, max_chars=180)
    assert len(sanitized.encode("utf-8")) <= 180
    assert len(sanitized) > 0


def test_disc_extraction_utility():
    album, disc = extract_disc_info("The Wall (Disc 2)")
    assert album == "The Wall"
    assert disc == 2

    album2, disc2 = extract_disc_info("Stadium Arcadium [CD 1]")
    assert album2 == "Stadium Arcadium"
    assert disc2 == 1

    album3, disc3 = extract_disc_info("Regular Album")
    assert album3 == "Regular Album"
    assert disc3 is None


def test_collision_handling(tmp_path):
    library_dir = tmp_path / "Music"
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=library_dir),
        organization=OrganizationConfig(collision_strategy="rename"),
    )
    organizer = LibraryOrganizer(config)

    meta = TrackMetadata(
        title="Song",
        artist="Artist",
        album="Album",
        track_number=1,
        date="2020",
    )

    source1 = tmp_path / "source1.opus"
    source1.write_bytes(b"audio version 1")
    dest1, _ = organizer.organize_track(source1, meta)
    assert dest1.name == "01 - Song.opus"
    assert dest1.exists()

    source2 = tmp_path / "source2.opus"
    source2.write_bytes(b"audio version 2 different content")
    dest2, _ = organizer.organize_track(source2, meta)
    assert dest2.name == "01 - Song (1).opus"
    assert dest2.exists()
    assert dest1.exists()
