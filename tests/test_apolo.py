
from apolo.config import ApoloConfig, DirectoriesConfig
from apolo.lyrics.lrclib import LRCLIBProvider
from apolo.metadata.itunes import iTunesProvider
from apolo.metadata.deezer import DeezerProvider
from apolo.metadata.models import TrackMetadata
from apolo.library.organizer import LibraryOrganizer
from apolo.utils import clean_track_title, sanitize_filename


def test_sanitize_filename():
    assert sanitize_filename("Artist/Track:Name?*") == "Artist／Track：Name？＊"
    assert sanitize_filename("Artist/Track:Name?*", replace_char="_") == "Artist_Track_Name"
    assert sanitize_filename("  clean  name  ") == "clean name"
    assert sanitize_filename("") == "Unknown"


def test_clean_track_title():
    title, artist = clean_track_title("Daft Punk - Get Lucky (Official Audio)")
    assert title == "Get Lucky"
    assert artist == "Daft Punk"

    title2, artist2 = clean_track_title("Queen - Bohemian Rhapsody [HD Remastered]")
    assert title2 == "Bohemian Rhapsody"
    assert artist2 == "Queen"


def test_metadata_providers_search(monkeypatch):
    class FakeResponse:
        def __init__(self, data):
            self._data = data
            self.status_code = 200

        def json(self):
            return self._data

    def fake_get(url, *args, **kwargs):
        if "itunes.apple.com" in url:
            return FakeResponse({
                "results": [
                    {
                        "trackName": "Get Lucky",
                        "artistName": "Daft Punk",
                        "collectionName": "Random Access Memories",
                        "releaseDate": "2013-05-17T07:00:00Z",
                    }
                ]
            })
        elif "api.deezer.com" in url:
            return FakeResponse({
                "data": [
                    {
                        "title": "Get Lucky",
                        "artist": {"name": "Daft Punk"},
                        "album": {"title": "Random Access Memories"},
                    }
                ]
            })
        return FakeResponse({})

    monkeypatch.setattr("requests.get", fake_get)

    itunes = iTunesProvider()
    results_itunes = itunes.search("Daft Punk Get Lucky", limit=2)
    assert len(results_itunes) > 0
    assert "Get Lucky" in results_itunes[0].title or "Daft Punk" in results_itunes[0].artist

    deezer = DeezerProvider()
    results_deezer = deezer.search("Daft Punk Get Lucky", limit=2)
    assert len(results_deezer) > 0
    assert "Get Lucky" in results_deezer[0].title or "Daft Punk" in results_deezer[0].artist


def test_lrclib_synced_lyrics(monkeypatch):
    class FakeResponse:
        status_code = 200

        def json(self):
            return {
                "syncedLyrics": "[00:01.00] Like the legend of the phoenix\n[00:05.00] All ends with beginnings"
            }

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: FakeResponse())

    lrclib = LRCLIBProvider()
    lyrics = lrclib.get_synced_lyrics("Get Lucky", "Daft Punk", duration=248)
    assert lyrics is not None
    assert "[" in lyrics and "]" in lyrics  # Has LRC timestamps


def test_library_organizer(tmp_path):
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=tmp_path / "Music")
    )
    organizer = LibraryOrganizer(config)

    meta = TrackMetadata(
        title="Get Lucky",
        artist="Daft Punk",
        album="Random Access Memories",
        track_number=8,
        date="2013-05-17",
        synced_lyrics="[00:01.00] Like the legend of the phoenix",
    )

    dest = organizer.get_destination_path(meta)
    assert dest == tmp_path / "Music" / "Daft Punk" / "Random Access Memories (2013)" / "08 - Get Lucky.opus"

    # Create dummy file to organize
    dummy_source = tmp_path / "dummy.opus"
    dummy_source.write_bytes(b"dummy audio")

    dest_audio, dest_lrc = organizer.organize_track(dummy_source, meta)
    assert dest_audio.exists()
    assert dest_lrc.exists()
    assert dest_lrc.read_text(encoding="utf-8") == meta.synced_lyrics
