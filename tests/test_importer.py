import json
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from typer.testing import CliRunner

from apolo.cli import app
from apolo.config import ApoloConfig, DirectoriesConfig
from apolo.importer import AppleMusicParser, DeezerParser, SpotifyParser, StreamingImporter


def test_deezer_parser_album():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "title": "Discovery",
        "artist": {"name": "Daft Punk"},
        "cover_xl": "https://e-cdns-images.dzcdn.net/images/cover/discovery.jpg",
        "release_date": "2001-03-12",
        "nb_tracks": 2,
        "tracks": {
            "data": [
                {
                    "title": "One More Time",
                    "artist": {"name": "Daft Punk"},
                    "track_position": 1,
                    "duration": 320,
                    "isrc": "FRZ010000001",
                },
                {
                    "title": "Aerodynamic",
                    "artist": {"name": "Daft Punk"},
                    "track_position": 2,
                    "duration": 207,
                    "isrc": "FRZ010000002",
                },
            ]
        },
    }

    with patch("requests.get", return_value=mock_response):
        collection = DeezerParser.parse("https://www.deezer.com/album/302127")
        assert collection is not None
        assert collection.title == "Discovery"
        assert collection.creator == "Daft Punk"
        assert len(collection.tracks) == 2
        assert collection.tracks[0].title == "One More Time"
        assert collection.tracks[0].track_number == 1
        assert collection.tracks[0].duration == 320.0
        assert collection.provider == "deezer"


def test_deezer_parser_playlist():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "title": "Synthwave Top Hits",
        "creator": {"name": "RetroWave"},
        "picture_xl": "https://e-cdns-images.dzcdn.net/images/playlist/synth.jpg",
        "tracks": {
            "data": [
                {
                    "title": "Nightcall",
                    "artist": {"name": "Kavinsky"},
                    "album": {"title": "OutRun", "cover_xl": "https://cover.jpg"},
                    "duration": 259,
                }
            ]
        },
    }

    with patch("requests.get", return_value=mock_response):
        collection = DeezerParser.parse("https://www.deezer.com/playlist/12345678")
        assert collection is not None
        assert collection.title == "Synthwave Top Hits"
        assert collection.creator == "RetroWave"
        assert len(collection.tracks) == 1
        assert collection.tracks[0].title == "Nightcall"


def test_spotify_parser_embed_html():
    embed_html = """
    <!DOCTYPE html>
    <html>
    <head>
    <script id="__NEXT_DATA__" type="application/json">
    {
        "props": {
            "pageProps": {
                "state": {
                    "data": {
                        "entity": {
                            "name": "Lo-Fi Beats",
                            "coverArt": {"sources": [{"url": "https://i.scdn.co/image/lofi.jpg"}]},
                            "trackList": [
                                {
                                    "title": "Snowman",
                                    "subtitle": "WYS",
                                    "duration": 180000,
                                    "isrc": "US1234567890"
                                }
                            ]
                        }
                    }
                }
            }
        }
    }
    </script>
    </head>
    </html>
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = embed_html

    with patch("requests.get", return_value=mock_response):
        collection = SpotifyParser.parse("https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M")
        assert collection is not None
        assert collection.title == "Lo-Fi Beats"
        assert len(collection.tracks) == 1
        assert collection.tracks[0].title == "Snowman"
        assert collection.tracks[0].artist == "WYS"
        assert collection.tracks[0].duration == 180.0
        assert collection.provider == "spotify"


def test_apple_music_parser():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "wrapperType": "collection",
                "collectionName": "Random Access Memories",
                "artistName": "Daft Punk",
                "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/100x100bb.jpg",
            },
            {
                "wrapperType": "track",
                "trackName": "Get Lucky",
                "artistName": "Daft Punk",
                "collectionName": "Random Access Memories",
                "trackNumber": 8,
                "trackCount": 13,
                "trackTimeMillis": 369000,
                "releaseDate": "2013-05-17T07:00:00Z",
                "artworkUrl100": "https://is1-ssl.mzstatic.com/image/thumb/100x100bb.jpg",
            },
        ]
    }

    with patch("requests.get", return_value=mock_response):
        collection = AppleMusicParser.parse("https://music.apple.com/us/album/random-access-memories/636988822")
        assert collection is not None
        assert collection.title == "Random Access Memories"
        assert collection.creator == "Daft Punk"
        assert len(collection.tracks) == 1
        assert collection.tracks[0].title == "Get Lucky"
        assert collection.tracks[0].track_number == 8
        assert collection.tracks[0].duration == 369.0


def test_importer_dry_run_simulation(tmp_path):
    library_dir = tmp_path / "Music"
    config = ApoloConfig(directories=DirectoriesConfig(library_dir=library_dir))
    importer = StreamingImporter(config)

    mock_collection = MagicMock()
    mock_collection.title = "Test Album"
    mock_collection.creator = "Test Artist"
    mock_collection.collection_type = "album"
    mock_collection.provider = "deezer"
    mock_collection.tracks = []

    with patch.object(DeezerParser, "parse", return_value=mock_collection):
        coll, results, pl_path = importer.import_collection("https://www.deezer.com/album/123", dry_run=True)
        assert coll is not None
        assert coll.title == "Test Album"


def test_cli_import_dry_run(tmp_path):
    runner = CliRunner()
    with patch.object(DeezerParser, "parse", return_value=None):
        result = runner.invoke(app, ["import", "https://invalid.com/url", "--dry-run"])
        assert result.exit_code == 0
        assert "Could not extract" in result.stdout
