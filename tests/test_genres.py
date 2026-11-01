import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch
from mutagen.oggopus import OggOpus

from apolo.config import ApoloConfig, DirectoriesConfig
from apolo.doctor import LibraryDoctor
from apolo.metadata.genres import (
    clean_genre,
    infer_genre_from_artist,
    normalize_genre,
)
from apolo.metadata.models import TrackMetadata


def create_dummy_opus(output_path: Path, title: str = "Song", artist: str = "Artist", album: str = "Album", genre: str = ""):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-t", "1", "-c:a", "libopus", "-b:a", "128k", str(output_path)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    f = OggOpus(output_path)
    f["TITLE"] = [title]
    f["ARTIST"] = [artist]
    f["ALBUM"] = [album]
    if genre:
        f["GENRE"] = [genre]
    f.save()


def test_normalize_genre_mappings():
    assert normalize_genre("Trap / Hip-Hop") == "Trap"
    assert normalize_genre("Trap / Urbano Latino") == "Trap Latino"
    assert normalize_genre("Urbano Latino / Trap") == "Trap Latino"
    assert normalize_genre("J-Core / Hardcore") == "J-Core"
    assert normalize_genre("Speedcore / Terrorcore") == "Speedcore"
    assert normalize_genre("Electronic; Dance; Techno") == "Techno"
    assert normalize_genre("música tropical") == "Música Tropical"
    assert normalize_genre("musica tropical") == "Música Tropical"
    assert normalize_genre("dance, électronique") == "Dance"
    assert normalize_genre("Game Soundtrack") == "Soundtrack"
    assert normalize_genre("hip-hop/rap") == "Hip-Hop"
    assert normalize_genre("Alternative / Pop") == "Pop Alternativo"


def test_normalize_genre_edge_cases():
    assert normalize_genre(None) is None
    assert normalize_genre("") is None
    assert normalize_genre("   ") is None
    assert normalize_genre("unknown") is None
    assert normalize_genre("<SIN GÉNERO>") is None
    # Unmapped genre is preserved
    assert normalize_genre("Custom Symphonic Metal") == "Custom Symphonic Metal"


def test_infer_genre_from_artist():
    assert infer_genre_from_artist("Laur") == "J-Core"
    assert infer_genre_from_artist("かめりあ") == "J-Core"
    assert infer_genre_from_artist("Camellia feat. Nanahira") == "J-Core"
    assert infer_genre_from_artist("tn-shi") == "Chiptune"
    assert infer_genre_from_artist("C.R.O") == "Urbano Latino"
    assert infer_genre_from_artist("Bardero$") == "Hip-Hop"
    assert infer_genre_from_artist("Random Unknown Indie Band") is None


def test_clean_genre_combines_normalization_and_inference():
    # 1. Existing genre normalizes
    assert clean_genre("Trap / Alternative", "Unknown") == "Trap"

    # 2. Missing genre infers from artist
    assert clean_genre(None, "Laur") == "J-Core"
    assert clean_genre("", "tn-shi") == "Chiptune"

    # 3. Missing genre and unknown artist returns None
    assert clean_genre("", "Unknown") is None


def test_track_metadata_auto_normalizes_genre():
    # Raw genre gets auto-normalized
    meta1 = TrackMetadata(title="Song 1", artist="Artist", genre="Trap / Hip-Hop")
    assert meta1.genre == "Trap"

    # Missing genre for known underground artist gets auto-inferred
    meta2 = TrackMetadata(title="Song 2", artist="Laur", genre=None)
    assert meta2.genre == "J-Core"

    meta3 = TrackMetadata(title="Song 3", artist="Unknown Artist", genre=None)
    assert meta3.genre is None


def test_doctor_fix_library_genres(tmp_path):
    library_dir = tmp_path / "Music"
    config = ApoloConfig(directories=DirectoriesConfig(library_dir=library_dir))
    doctor = LibraryDoctor(config)

    # Track 1: Unnormalized genre ("Trap / Hip-Hop")
    p1 = library_dir / "Artist1" / "Album1 (2024)" / "01 - Hit.opus"
    create_dummy_opus(p1, title="Hit", artist="Artist1", genre="Trap / Hip-Hop")

    # Track 2: Missing genre, known artist ("Laur")
    p2 = library_dir / "Laur" / "Album2 (2024)" / "01 - Energy.opus"
    create_dummy_opus(p2, title="Energy", artist="Laur", genre="")

    # Track 3: Missing genre, resolved via mocked iTunes
    p3 = library_dir / "Daft Punk" / "RAM (2013)" / "01 - Get Lucky.opus"
    create_dummy_opus(p3, title="Get Lucky", artist="Daft Punk", genre="")

    # Track 4: Already normalized ("Techno")
    p4 = library_dir / "DJ" / "Set (2024)" / "01 - Rave.opus"
    create_dummy_opus(p4, title="Rave", artist="DJ", genre="Techno")

    # Mock iTunes search for Track 3
    fake_itunes_track = MagicMock()
    fake_itunes_track.genre = "Dance, Électronique"
    with patch.object(doctor.matcher.itunes, "search", return_value=[fake_itunes_track]):
        # 1. Test Dry Run
        dry_summary = doctor.fix_library_genres(library_dir=library_dir, dry_run=True)
        assert dry_summary["total_scanned"] == 4
        assert dry_summary["modified"] == 3
        assert dry_summary["already_normalized"] == 1
        assert len(dry_summary["changes"]) == 3

        # Verify disk was NOT modified during dry-run
        f1_check = OggOpus(p1)
        assert f1_check["GENRE"] == ["Trap / Hip-Hop"]

        # 2. Test Apply Run
        apply_summary = doctor.fix_library_genres(library_dir=library_dir, dry_run=False)
        assert apply_summary["modified"] == 3

        # Verify disk WAS updated
        f1_after = OggOpus(p1)
        assert f1_after["GENRE"] == ["Trap"]

        f2_after = OggOpus(p2)
        assert f2_after["GENRE"] == ["J-Core"]

        f3_after = OggOpus(p3)
        assert f3_after["GENRE"] == ["Dance"]
