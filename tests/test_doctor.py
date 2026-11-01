import io
import subprocess
from pathlib import Path
from typing import Optional
from PIL import Image
from typer.testing import CliRunner

from apolo.cli import app
from apolo.config import ApoloConfig, DirectoriesConfig, load_config
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


def test_doctor_controlled_anomalies(tmp_path):
    library_dir = tmp_path / "Music"
    from apolo.config import DoctorConfig

    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=library_dir),
        doctor=DoctorConfig(controlled_anomalies=["Justice - Cross", "Bardero$ - PURE DRUG"]),
    )
    doctor = LibraryDoctor(config)

    # 1. Controlled incomplete album (Justice - Cross has 1/2 tracks, but matches controlled rule)
    alb_dir1 = library_dir / "Justice" / "Cross (2007)"
    create_dummy_opus(alb_dir1 / "01 - Genesis.opus", title="Genesis", artist="Justice", album="Cross", track_number=1, track_total=2)

    # 2. Uncontrolled incomplete album (Daft Punk - Discovery has 1/2 tracks)
    alb_dir2 = library_dir / "Daft Punk" / "Discovery (2001)"
    create_dummy_opus(alb_dir2 / "01 - One More Time.opus", title="One More Time", artist="Daft Punk", album="Discovery", track_number=1, track_total=2)

    report = doctor.scan_library(library_dir=library_dir)
    assert report.total_tracks == 2
    assert report.total_albums == 2
    assert len(report.incomplete_albums) == 1
    assert report.incomplete_albums[0].album_title == "Discovery"

    assert len(report.controlled_incomplete_albums) == 1
    assert report.controlled_incomplete_albums[0].album_title == "Cross"

    # Only 1 uncontrolled album penalizes health score (-10 pts)
    assert report.health_score == 90.0


def test_doctor_controlled_anomalies_tag(tmp_path):
    library_dir = tmp_path / "Music"
    config = ApoloConfig(directories=DirectoriesConfig(library_dir=library_dir))
    doctor = LibraryDoctor(config)

    # Create incomplete album with controlled_anomaly vorbis tag
    alb_dir = library_dir / "C.R.O" / "Malos Cantores (2024)"
    p = alb_dir / "01 - Hit.opus"
    create_dummy_opus(p, title="Hit", artist="C.R.O", album="Malos Cantores", track_number=1, track_total=10)

    # Tag with CONTROLLED_ANOMALY
    from apolo.tagger import AudioTagger
    AudioTagger.update_tags(p, {"controlled_anomaly": True})

    report = doctor.scan_library(library_dir=library_dir)
    assert len(report.incomplete_albums) == 0
    assert len(report.controlled_incomplete_albums) == 1
    assert report.controlled_incomplete_albums[0].album_title == "Malos Cantores"
    assert report.health_score == 100.0


def test_doctor_cli_control_command(tmp_path):
    runner = CliRunner()

    import os
    os.environ["XDG_CONFIG_HOME"] = str(tmp_path)

    # Add control rule
    res1 = runner.invoke(app, ["doctor", "--control", "C.R.O - Malos Cantores"])
    assert res1.exit_code == 0
    assert "Added controlled anomaly rule" in res1.stdout

    # Verify saved
    loaded = load_config()
    assert "C.R.O - Malos Cantores" in loaded.doctor.controlled_anomalies

    # Remove rule
    res2 = runner.invoke(app, ["doctor", "--uncontrol", "C.R.O - Malos Cantores"])
    assert res2.exit_code == 0
    assert "Removed controlled anomaly rule" in res2.stdout

    loaded2 = load_config()
    assert "C.R.O - Malos Cantores" not in loaded2.doctor.controlled_anomalies


def test_doctor_show_controlled_anomalies_config(tmp_path):
    # Test config loading
    cfg_file = tmp_path / "apolo" / "config.toml"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text(
        """
[doctor]
show_controlled_anomalies = false
controlled_anomalies = ["Justice - Cross"]
""",
        encoding="utf-8",
    )

    loaded = load_config(cfg_file)
    assert loaded.doctor.show_controlled_anomalies is False
    assert loaded.doctor.controlled_anomalies == ["Justice - Cross"]

    # Test saving controlled anomalies preserves show_controlled_anomalies
    from apolo.config import save_doctor_controlled_anomalies
    save_doctor_controlled_anomalies(["Justice - Cross", "Daft Punk - Discovery"], config_path=cfg_file)
    
    loaded_after = load_config(cfg_file)
    assert loaded_after.doctor.show_controlled_anomalies is False
    assert "Justice - Cross" in loaded_after.doctor.controlled_anomalies
    assert "Daft Punk - Discovery" in loaded_after.doctor.controlled_anomalies


def test_doctor_show_controlled_anomalies_cli(tmp_path):
    runner = CliRunner()
    import os
    os.environ["XDG_CONFIG_HOME"] = str(tmp_path)

    library_dir = tmp_path / "Music"
    cfg_dir = tmp_path / "apolo"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / "config.toml"

    # Create dummy album with controlled anomaly
    alb_dir = library_dir / "Justice" / "Cross (2007)"
    create_dummy_opus(alb_dir / "01 - Genesis.opus", title="Genesis", artist="Justice", album="Cross", track_number=1, track_total=2)

    # 1. Default config (show_controlled_anomalies = true): table should appear
    cfg_file.write_text(
        f"""
[directories]
library_dir = "{library_dir}"

[doctor]
show_controlled_anomalies = true
controlled_anomalies = ["Justice - Cross"]
""",
        encoding="utf-8",
    )

    res1 = runner.invoke(app, ["doctor", "--dir", str(library_dir)])
    assert res1.exit_code == 0
    assert "Controlled Anomalies" in res1.stdout
    assert "Cross" in res1.stdout

    # 2. Config disabled (show_controlled_anomalies = false): detailed table should NOT appear, but summary still shows count
    cfg_file.write_text(
        f"""
[directories]
library_dir = "{library_dir}"

[doctor]
show_controlled_anomalies = false
controlled_anomalies = ["Justice - Cross"]
""",
        encoding="utf-8",
    )

    res2 = runner.invoke(app, ["doctor", "--dir", str(library_dir)])
    assert res2.exit_code == 0
    assert "Álbumes Parciales Controlados" not in res2.stdout
    assert "Controlled Anomalies:    1" in res2.stdout

    # 3. Explicit --show-controlled overrides false config
    res3 = runner.invoke(app, ["doctor", "--dir", str(library_dir), "--show-controlled"])
    assert res3.exit_code == 0
    assert "Álbumes Parciales Controlados" in res3.stdout
    assert "Cross" in res3.stdout

    # 4. Explicit --controlled displays controlled anomalies only
    res4 = runner.invoke(app, ["doctor", "--dir", str(library_dir), "--controlled"])
    assert res4.exit_code == 0
    assert "Álbumes Parciales Controlados" in res4.stdout
    assert "Cross" in res4.stdout


def test_doctor_show_missing_lyrics_config(tmp_path):
    cfg_file = tmp_path / "apolo" / "config.toml"
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    cfg_file.write_text(
        """
[doctor]
show_missing_lyrics = false
""",
        encoding="utf-8",
    )

    loaded = load_config(cfg_file)
    assert loaded.doctor.show_missing_lyrics is False


def test_doctor_show_missing_lyrics_cli(tmp_path):
    runner = CliRunner()
    import os
    os.environ["XDG_CONFIG_HOME"] = str(tmp_path)

    library_dir = tmp_path / "Music"
    cfg_dir = tmp_path / "apolo"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    cfg_file = cfg_dir / "config.toml"

    # Create dummy album missing lyrics
    alb_dir = library_dir / "Justice" / "Cross (2007)"
    create_dummy_opus(alb_dir / "01 - Genesis.opus", title="Genesis", artist="Justice", album="Cross", track_number=1, track_total=1, lyrics="")

    # 1. Default config (show_missing_lyrics = true): table should appear
    cfg_file.write_text(
        f"""
[directories]
library_dir = "{library_dir}"

[doctor]
show_missing_lyrics = true
""",
        encoding="utf-8",
    )

    res1 = runner.invoke(app, ["doctor", "--dir", str(library_dir)])
    assert res1.exit_code == 0
    assert "Tracks Missing Synced Lyrics" in res1.stdout

    # 2. Config disabled (show_missing_lyrics = false): table should NOT appear, but summary still shows count
    cfg_file.write_text(
        f"""
[directories]
library_dir = "{library_dir}"

[doctor]
show_missing_lyrics = false
""",
        encoding="utf-8",
    )

    res2 = runner.invoke(app, ["doctor", "--dir", str(library_dir)])
    assert res2.exit_code == 0
    assert "Tracks Missing Synced Lyrics" not in res2.stdout
    assert "Missing Synced Lyrics:   1" in res2.stdout

    # 3. Explicit --show-lyrics overrides false config
    res3 = runner.invoke(app, ["doctor", "--dir", str(library_dir), "--show-lyrics"])
    assert res3.exit_code == 0
    assert "Tracks Missing Synced Lyrics" in res3.stdout

    # 4. Explicit --missing-lyrics displays missing lyrics table only
    res4 = runner.invoke(app, ["doctor", "--dir", str(library_dir), "--missing-lyrics"])
    assert res4.exit_code == 0
    assert "Tracks Missing Synced Lyrics" in res4.stdout




