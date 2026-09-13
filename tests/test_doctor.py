import io
import subprocess
from pathlib import Path
from PIL import Image
import pytest
from typer.testing import CliRunner

from apolo.cli import app
from apolo.config import ApoloConfig, DirectoriesConfig
from apolo.doctor import LibraryDoctor
from apolo.metadata.models import TrackMetadata
from apolo.tagger import AudioTagger


def create_dummy_opus(
    output_path: Path,
    title: str = "Song",
    artist: str = "Artist",
    album: str = "Album",
    track_number: int = 1,
    track_total: int = 10,
    disc_number: Optional[int] = None,
    disc_total: Optional[int] = None,
    date: str = "2024",
    genre: str = "Synthwave",
    has_cover: bool = True,
    lyrics: str = "[00:01.00] Line 1",
):
    """Generates a 1-second silence Opus file with custom metadata."""
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

    cover_bytes = None
    if has_cover:
        img = Image.new("RGB", (600, 600), color="purple")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        cover_bytes = buf.getvalue()

    meta = TrackMetadata(
        title=title,
        artist=artist,
        album=album,
        track_number=track_number,
        track_total=track_total,
        disc_number=disc_number,
        disc_total=disc_total,
        date=date,
        genre=genre,
        cover_art_data=cover_bytes,
        synced_lyrics=lyrics,
    )
    AudioTagger.tag_opus(output_path, meta)


def test_doctor_scan_and_incomplete_albums(tmp_path):
    library_dir = tmp_path / "Music"
    config = ApoloConfig(directories=DirectoriesConfig(library_dir=library_dir))
    doctor = LibraryDoctor(config)

    # Create an incomplete album (track total = 3, but tracks 1 and 3 are present, 2 is missing)
    alb_dir = library_dir / "Kavinsky" / "OutRun (2013)"
    create_dummy_opus(alb_dir / "01 - Prelude.opus", title="Prelude", artist="Kavinsky", album="OutRun", track_number=1, track_total=3)
    create_dummy_opus(alb_dir / "03 - Nightcall.opus", title="Nightcall", artist="Kavinsky", album="OutRun", track_number=3, track_total=3)

    report = doctor.scan_library(library_dir=library_dir)
    assert report.total_tracks == 2
    assert len(report.incomplete_albums) == 1

    inc_album = report.incomplete_albums[0]
    assert inc_album.album_title == "OutRun"
    assert inc_album.missing_tracks == [2]
    assert inc_album.present_tracks == [1, 3]


def test_doctor_duplicates_detection(tmp_path):
    library_dir = tmp_path / "Music"
    config = ApoloConfig(directories=DirectoriesConfig(library_dir=library_dir))
    doctor = LibraryDoctor(config)

    # Create duplicate track in two different folders
    create_dummy_opus(library_dir / "Artist" / "Album1" / "01 - Hit.opus", title="Hit Song", artist="Top Artist")
    create_dummy_opus(library_dir / "Artist" / "Singles" / "Hit.opus", title="Hit Song", artist="Top Artist")

    report = doctor.scan_library(library_dir=library_dir)
    assert len(report.duplicates) >= 1
    dup = report.duplicates[0]
    assert "Hit" in dup.title
    assert len(dup.tracks) == 2


def test_doctor_missing_lyrics_and_covers(tmp_path):
    library_dir = tmp_path / "Music"
    config = ApoloConfig(directories=DirectoriesConfig(library_dir=library_dir))
    doctor = LibraryDoctor(config)

    # Track missing lyrics and cover
    no_meta_track = library_dir / "Unknown" / "Single" / "01 - Raw.opus"
    create_dummy_opus(no_meta_track, title="Raw", artist="Artist", has_cover=False, lyrics=None)

    report = doctor.scan_library(library_dir=library_dir)
    assert len(report.missing_lyrics) == 1
    assert no_meta_track in report.missing_lyrics
    assert len(report.missing_or_lowres_covers) == 1


def test_doctor_cli_command(tmp_path):
    runner = CliRunner()
    library_dir = tmp_path / "Music"
    alb_dir = library_dir / "Justice" / "Cross (2007)"
    create_dummy_opus(alb_dir / "01 - Genesis.opus", title="Genesis", artist="Justice", album="Cross", track_number=1, track_total=2)

    result = runner.invoke(app, ["doctor", "--dir", str(library_dir)])
    assert result.exit_code == 0
    assert "Health Score" in result.stdout
    assert "Genesis" or "Cross" in result.stdout


def test_doctor_multi_disc_completeness(tmp_path):
    library_dir = tmp_path / "Music"
    config = ApoloConfig(directories=DirectoriesConfig(library_dir=library_dir))
    doctor = LibraryDoctor(config)

    alb_dir = library_dir / "Tanger" / "Prefer not to say (2024)"
    # Create 3 discs with 2 tracks each (total 6 tracks)
    for d in [1, 2, 3]:
        for t in [1, 2]:
            create_dummy_opus(
                alb_dir / f"Disc 0{d}" / f"0{t} - Song D{d}T{t}.opus",
                title=f"Song D{d}T{t}",
                artist="Tanger",
                album="Prefer not to say",
                track_number=t,
                track_total=2,
                disc_number=d,
                disc_total=3,
            )

    report = doctor.scan_library(library_dir=library_dir)
    assert report.total_tracks == 6
    assert report.total_albums == 1
    assert len(report.incomplete_albums) == 0
    assert report.health_score == 100.0

