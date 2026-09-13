import io
import subprocess
from pathlib import Path
from PIL import Image
import pytest
from typer.testing import CliRunner

from apolo.cli import app
from apolo.config import ApoloConfig, DirectoriesConfig
from apolo.metadata.models import TrackMetadata
from apolo.playlists import PlaylistManager
from apolo.tagger import AudioTagger


def create_dummy_opus(
    output_path: Path,
    title: str = "Song",
    artist: str = "Artist",
    album: str = "Album",
    date: str = "2024",
    genre: str = "Electronic",
    origin: str = "local",
):
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
    meta = TrackMetadata(
        title=title,
        artist=artist,
        album=album,
        date=date,
        genre=genre,
        origin=origin,
    )
    AudioTagger.tag_opus(output_path, meta)


def test_playlist_smart_create_and_list(tmp_path):
    library_dir = tmp_path / "Music"
    config = ApoloConfig(directories=DirectoriesConfig(library_dir=library_dir))
    pm = PlaylistManager(config)

    # Create several tracks with different genres and years
    t1 = library_dir / "Daft Punk" / "Discovery (2001)" / "01 - One More Time.opus"
    create_dummy_opus(t1, title="One More Time", artist="Daft Punk", album="Discovery", date="2001", genre="French House")

    t2 = library_dir / "Kavinsky" / "OutRun (2013)" / "01 - Nightcall.opus"
    create_dummy_opus(t2, title="Nightcall", artist="Kavinsky", album="OutRun", date="2013", genre="Synthwave")

    t3 = library_dir / "Carpenter Brut" / "Trilogy (2015)" / "01 - Turbo Killer.opus"
    create_dummy_opus(t3, title="Turbo Killer", artist="Carpenter Brut", album="Trilogy", date="2015", genre="Synthwave")

    # Create smart playlist for Synthwave
    pl_path, count = pm.create_smart_playlist(name="Synthwave Hits", genre="Synthwave")
    assert pl_path.exists()
    assert count == 2

    # Verify playlist inspection and listing
    playlists = pm.list_playlists()
    assert len(playlists) == 1
    pl_info = playlists[0]
    assert pl_info.name == "Synthwave Hits"
    assert pl_info.valid_tracks == 2
    assert pl_info.broken_tracks == 0


def test_playlist_repair(tmp_path):
    library_dir = tmp_path / "Music"
    config = ApoloConfig(directories=DirectoriesConfig(library_dir=library_dir))
    pm = PlaylistManager(config)

    # Track initially placed in OldFolder
    old_track_path = library_dir / "OldFolder" / "01 - Classic.opus"
    create_dummy_opus(old_track_path, title="Classic", artist="Artist")

    # Create playlist pointing to OldFolder
    pl_path, count = pm.create_manual_playlist("MyList", [old_track_path])
    assert count == 1

    # Simulate reorganizing/relocating file to NewFolder
    new_dir = library_dir / "Artist" / "Album (2024)"
    new_dir.mkdir(parents=True, exist_ok=True)
    new_track_path = new_dir / "01 - Classic.opus"
    old_track_path.rename(new_track_path)

    # Before repair, playlist has 1 broken track
    info_before = pm.inspect_playlist(pl_path)
    assert info_before.broken_tracks == 1

    # Run repair
    repaired = pm.repair_playlists()
    assert pl_path.name in repaired
    assert repaired[pl_path.name] == 1

    # After repair, playlist is valid again
    info_after = pm.inspect_playlist(pl_path)
    assert info_after.broken_tracks == 0
    assert info_after.valid_tracks == 1


def test_playlist_export(tmp_path):
    library_dir = tmp_path / "Music"
    export_dir = tmp_path / "ExportUSB"
    config = ApoloConfig(directories=DirectoriesConfig(library_dir=library_dir))
    pm = PlaylistManager(config)

    track_path = library_dir / "Artist" / "01 - Song.opus"
    create_dummy_opus(track_path, title="Song", artist="Artist")

    pl_path, _ = pm.create_manual_playlist("Roadtrip", [track_path])

    exported_pl, copied_count = pm.export_playlist("Roadtrip", export_dir, copy_files=True)
    assert exported_pl.exists()
    assert copied_count == 1
    assert (export_dir / "01 - Song.opus").exists()


def test_playlist_cli_commands(tmp_path):
    runner = CliRunner()
    # Test playlist list
    res_list = runner.invoke(app, ["playlist", "list"])
    assert res_list.exit_code == 0
