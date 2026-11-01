from pathlib import Path

import pytest

from apolo.config import ApoloConfig, DirectoriesConfig, OrganizationConfig
from apolo.library.organizer import LibraryOrganizer
from apolo.library.template import PathTemplateEngine, extract_decade, extract_initial
from apolo.metadata.models import TrackMetadata


def test_extract_initial():
    assert extract_initial("Daft Punk") == "D"
    assert extract_initial("Édith Piaf") == "E"
    assert extract_initial("¡Viva La Vida!") == "V"
    assert extract_initial("100 gecs") == "#"
    assert extract_initial("...And You Will Know Us") == "A"
    assert extract_initial(None) == "#"
    assert extract_initial("") == "#"


def test_extract_decade():
    assert extract_decade("1979-11-30") == "1970s"
    assert extract_decade("1984") == "1980s"
    assert extract_decade("2001-03-12") == "2000s"
    assert extract_decade("2024") == "2020s"
    assert extract_decade("Unknown Year") == "Unknown Decade"
    assert extract_decade(None) == "Unknown Decade"


def test_default_template_regression(tmp_path: Path):
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=tmp_path / "Music"),
        organization=OrganizationConfig(
            path_template="{artist}/{album} ({date})/{track:02d} - {title}.opus"
        ),
    )
    organizer = LibraryOrganizer(config)

    meta = TrackMetadata(
        title="Digital Love",
        artist="Daft Punk",
        album="Discovery",
        track_number=3,
        date="2001",
    )
    dest = organizer.get_destination_path(meta)
    assert dest == tmp_path / "Music" / "Daft Punk" / "Discovery (2001)" / "03 - Digital Love.opus"


def test_custom_template_genre_and_year(tmp_path: Path):
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=tmp_path / "Music"),
        organization=OrganizationConfig(
            path_template="{genre}/{artist}/{album} ({year})/{track:02d} - {title}.opus"
        ),
    )
    organizer = LibraryOrganizer(config)

    meta = TrackMetadata(
        title="Digital Love",
        artist="Daft Punk",
        album="Discovery",
        track_number=3,
        date="2001-03-12",
        genre="French House",
    )
    dest = organizer.get_destination_path(meta)
    assert (
        dest
        == tmp_path
        / "Music"
        / "French House"
        / "Daft Punk"
        / "Discovery (2001)"
        / "03 - Digital Love.opus"
    )


def test_custom_template_initial_az(tmp_path: Path):
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=tmp_path / "Music"),
        organization=OrganizationConfig(
            path_template="{initial}/{artist}/{album} ({year})/{track:02d} - {title}.opus"
        ),
    )
    organizer = LibraryOrganizer(config)

    meta1 = TrackMetadata(
        title="La Vie en rose",
        artist="Édith Piaf",
        album="Chansons",
        track_number=1,
        date="1947",
    )
    meta2 = TrackMetadata(
        title="Stupid Horse",
        artist="100 gecs",
        album="1000 gecs",
        track_number=4,
        date="2019",
    )

    dest1 = organizer.get_destination_path(meta1)
    dest2 = organizer.get_destination_path(meta2)

    assert (
        dest1
        == tmp_path / "Music" / "E" / "Édith Piaf" / "Chansons (1947)" / "01 - La Vie en rose.opus"
    )
    assert (
        dest2
        == tmp_path / "Music" / "#" / "100 gecs" / "1000 gecs (2019)" / "04 - Stupid Horse.opus"
    )


def test_custom_template_decade(tmp_path: Path):
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=tmp_path / "Music"),
        organization=OrganizationConfig(
            path_template="{decade}/{artist} - {album}/{track:02d} - {title}.opus"
        ),
    )
    organizer = LibraryOrganizer(config)

    meta = TrackMetadata(
        title="Blue Monday",
        artist="New Order",
        album="Power, Corruption & Lies",
        track_number=1,
        date="1983-03-07",
    )
    dest = organizer.get_destination_path(meta)
    assert (
        dest
        == tmp_path
        / "Music"
        / "1980s"
        / "New Order - Power, Corruption & Lies"
        / "01 - Blue Monday.opus"
    )


def test_custom_template_flat_artist(tmp_path: Path):
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=tmp_path / "Music"),
        organization=OrganizationConfig(path_template="{artist}/{track:02d} - {title}.opus"),
    )
    organizer = LibraryOrganizer(config)

    meta = TrackMetadata(
        title="Genesis",
        artist="Justice",
        album="Cross",
        track_number=1,
        date="2007",
    )
    dest = organizer.get_destination_path(meta)
    assert dest == tmp_path / "Music" / "Justice" / "01 - Genesis.opus"


def test_custom_template_preserves_lossless_flac(tmp_path: Path):
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=tmp_path / "Music"),
        organization=OrganizationConfig(
            path_template="{genre}/{artist}/{album}/{track:02d} - {title}.opus"
        ),
    )
    organizer = LibraryOrganizer(config)

    meta = TrackMetadata(
        title="Giorgio by Moroder",
        artist="Daft Punk",
        album="Random Access Memories",
        track_number=3,
        date="2013",
        genre="Disco",
    )
    # File is FLAC, so extension should automatically be .flac
    dest = organizer.get_destination_path(meta, extension=".flac")
    assert dest.suffix == ".flac"
    assert dest.name == "03 - Giorgio by Moroder.flac"


def test_custom_template_multi_disc_handling(tmp_path: Path):
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=tmp_path / "Music"),
        organization=OrganizationConfig(
            path_template="{artist}/{album} ({year})/{track:02d} - {title}.opus",
            multi_disc_folder=True,
        ),
    )
    organizer = LibraryOrganizer(config)

    meta_disc2 = TrackMetadata(
        title="Hey You",
        artist="Pink Floyd",
        album="The Wall",
        track_number=1,
        disc_number=2,
        disc_total=2,
        date="1979",
    )
    dest = organizer.get_destination_path(meta_disc2)
    assert "Disc 02" in str(dest)
    assert dest.name == "01 - Hey You.opus"


def test_custom_template_group_singles(tmp_path: Path):
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=tmp_path / "Music"),
        organization=OrganizationConfig(
            path_template="{genre}/{artist}/{album} ({year})/{track:02d} - {title}.opus",
            group_singles=True,
        ),
    )
    organizer = LibraryOrganizer(config)

    meta_single = TrackMetadata(
        title="Starboy",
        artist="The Weeknd",
        album="Single",
        track_number=1,
        date="2016",
        genre="R&B",
    )
    dest = organizer.get_destination_path(meta_single)
    assert dest == tmp_path / "Music" / "R&B" / "The Weeknd" / "Singles" / "Starboy (2016).opus"


def test_unknown_variable_raises_error():
    engine = PathTemplateEngine()
    meta = TrackMetadata(title="Song", artist="Artist")
    with pytest.raises(ValueError, match="Unknown template variable '{nonexistent}'"):
        engine.render_parts("{artist}/{nonexistent}/{title}.opus", meta)
