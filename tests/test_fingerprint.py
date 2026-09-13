import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest

from apolo.config import ApoloConfig
from apolo.fingerprint import AcousticFingerprinter
from apolo.metadata.models import TrackMetadata


def test_fingerprint_file_missing(tmp_path: Path):
    fp = AcousticFingerprinter()
    dur, fingerprint = fp.fingerprint_file(tmp_path / "nonexistent.opus")
    assert dur is None
    assert fingerprint is None


def test_fingerprint_file_mocked(tmp_path: Path, monkeypatch):
    dummy_file = tmp_path / "audio.opus"
    dummy_file.write_bytes(b"dummy")

    fingerprinter = AcousticFingerprinter()
    monkeypatch.setattr(fingerprinter, "is_fpcalc_available", lambda: True)

    mock_json = json.dumps({"duration": 210.5, "fingerprint": "AQAA-1GkmYmkKEmUCXgA"})
    mock_run = MagicMock()
    mock_run.returncode = 0
    mock_run.stdout = mock_json

    monkeypatch.setattr("subprocess.run", lambda *args, **kwargs: mock_run)

    dur, fp_str = fingerprinter.fingerprint_file(dummy_file)
    assert dur == 210.5
    assert fp_str == "AQAA-1GkmYmkKEmUCXgA"


def test_lookup_fingerprint_mocked(monkeypatch):
    fingerprinter = AcousticFingerprinter()

    mock_response_data = {
        "status": "ok",
        "results": [
            {
                "id": "result-1",
                "score": 0.98,
                "recordings": [
                    {
                        "id": "mbid-12345",
                        "title": "Around The World",
                        "artists": [{"name": "Daft Punk"}],
                        "duration": 429,
                        "releasegroups": [
                            {
                                "id": "rg-1",
                                "title": "Homework",
                                "artists": [{"name": "Daft Punk"}],
                                "releases": [
                                    {
                                        "id": "rel-1",
                                        "date": {"year": 1997},
                                        "mediums": [
                                            {
                                                "position": 1,
                                                "medium_count": 1,
                                                "tracks": [{"position": 7, "track_count": 16}],
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = mock_response_data

    monkeypatch.setattr("requests.get", lambda *args, **kwargs: mock_resp)

    results = fingerprinter.lookup_fingerprint(429.0, "AQAA-1GkmYmkKEmUCXgA")
    assert len(results) == 1
    track = results[0]
    assert track.title == "Around The World"
    assert track.artist == "Daft Punk"
    assert track.album == "Homework"
    assert track.track_number == 7
    assert track.date == "1997"
    assert track.provider_source == "acoustid"
    assert track.source_id == "mbid-12345"


def test_identify_file_integration(tmp_path: Path, monkeypatch):
    dummy_file = tmp_path / "song.flac"
    dummy_file.write_bytes(b"dummy flac data")

    fingerprinter = AcousticFingerprinter()
    monkeypatch.setattr(fingerprinter, "fingerprint_file", lambda f: (180.0, "AQAA-TEST"))

    matched_track = TrackMetadata(
        title="Identified Song",
        artist="Identified Artist",
        album="Identified Album",
    )
    monkeypatch.setattr(fingerprinter, "lookup_fingerprint", lambda dur, fp: [matched_track])

    meta = fingerprinter.identify_file(dummy_file)
    assert meta is not None
    assert meta.title == "Identified Song"
    assert meta.artist == "Identified Artist"
