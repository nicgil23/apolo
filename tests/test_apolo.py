import os
import tempfile
from pathlib import Path
import pytest
from mutagen.oggopus import OggOpus

from apolo.config import ApoloConfig, DirectoriesConfig
from apolo.lyrics.lrclib import LRCLIBProvider
from apolo.metadata.itunes import iTunesProvider
from apolo.metadata.deezer import DeezerProvider
from apolo.metadata.matcher import MetadataMatcher
from apolo.metadata.models import METADATOS_BIBLIOTECA, TrackMetadata
from apolo.organizer import LibraryOrganizer
from apolo.tagger import AudioTagger
from apolo.utils import clean_track_title, sanitize_filename


def test_sanitize_filename():
    assert sanitize_filename("Artist/Track:Name?*") == "Artist_Track_Name"
    assert sanitize_filename("  clean  name  ") == "clean name"
    assert sanitize_filename("") == "Unknown"


def test_clean_track_title():
    title, artist = clean_track_title("Daft Punk - Get Lucky (Official Audio)")
    assert title == "Get Lucky"
    assert artist == "Daft Punk"

    title2, artist2 = clean_track_title("Queen - Bohemian Rhapsody [HD Remastered]")
    assert title2 == "Bohemian Rhapsody"
    assert artist2 == "Queen"


def test_metadata_providers_search():
    itunes = iTunesProvider()
    results_itunes = itunes.search("Daft Punk Get Lucky", limit=2)
    assert len(results_itunes) > 0
    assert "Get Lucky" in results_itunes[0].title or "Daft Punk" in results_itunes[0].artist

    deezer = DeezerProvider()
    results_deezer = deezer.search("Daft Punk Get Lucky", limit=2)
    assert len(results_deezer) > 0
    assert "Get Lucky" in results_deezer[0].title or "Daft Punk" in results_deezer[0].artist


def test_lrclib_synced_lyrics():
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
