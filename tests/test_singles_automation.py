import subprocess
from pathlib import Path
from mutagen.oggopus import OggOpus

from apolo.config import ApoloConfig, DirectoriesConfig
from apolo.doctor import LibraryDoctor
from apolo.metadata.models import TrackMetadata
from apolo.organizer import LibraryOrganizer
from apolo.tagger import AudioTagger


def create_dummy_opus(output_path: Path, title="Song", artist="Artist", album="Album", date="2024"):
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
    f["DATE"] = [date]
    f.save()


def test_track_metadata_normalizes_single_album():
    # When album is None
    m1 = TrackMetadata(title="Mood Swing", artist="tn-shi", album=None)
    assert m1.album == "Mood Swing - Single"

    # When album is "Single"
    m2 = TrackMetadata(title="Revelation", artist="tn-shi", album="Single")
    assert m2.album == "Revelation - Single"

    # When album is "Singles"
    m3 = TrackMetadata(title="INVERSION", artist="tn-shi", album="Singles")
    assert m3.album == "INVERSION - Single"

    # When album is explicit album title
    m4 = TrackMetadata(title="Tomorrow", artist="FreeTEMPO", album="Life")
    assert m4.album == "Life"


def test_organizer_routes_singles_to_singles_dir(tmp_path):
    library_dir = tmp_path / "Library"
    config = ApoloConfig(directories=DirectoriesConfig(library_dir=library_dir))
    organizer = LibraryOrganizer(config)

    meta = TrackMetadata(title="Mood Swing", artist="tn-shi", album="Mood Swing - Single", date="2024-07-20")
    dest = organizer.get_destination_path(meta)
    assert dest == library_dir / "tn-shi" / "Singles" / "Mood Swing (2024).opus"


def test_tagger_writes_single_album_tag(tmp_path):
    opus_path = tmp_path / "test_song.opus"
    create_dummy_opus(opus_path, title="Test Single", artist="Artist", album="Single", date="2023")

    meta = TrackMetadata(title="Test Single", artist="Artist", album="Single", date="2023")
    AudioTagger.tag_opus(opus_path, meta)

    audio = OggOpus(opus_path)
    assert audio.get("ALBUM") == ["Test Single - Single"]
    assert audio.get("TITLE") == ["Test Single"]
    assert audio.get("ARTIST") == ["Artist"]


def test_doctor_ignores_singles_for_incomplete_albums(tmp_path):
    library_dir = tmp_path / "Library"
    song_path = library_dir / "tn-shi" / "Singles" / "Mood Swing (2024).opus"
    create_dummy_opus(song_path, title="Mood Swing", artist="tn-shi", album="Mood Swing - Single", date="2024")

    config = ApoloConfig(directories=DirectoriesConfig(library_dir=library_dir))
    doctor = LibraryDoctor(config)
    report = doctor.scan_library(library_dir=library_dir)

    assert len(report.incomplete_albums) == 0
    assert len(report.controlled_incomplete_albums) == 0
