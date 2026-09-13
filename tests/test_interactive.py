from pathlib import Path
from typing import List, Tuple
from unittest.mock import MagicMock
import pytest

from apolo.config import ApoloConfig, DirectoriesConfig
from apolo.metadata.matcher import MetadataMatcher
from apolo.metadata.models import TrackMetadata
from apolo.pipeline import ProcessingPipeline


def test_matcher_get_ranked_candidates(monkeypatch):
    matcher = MetadataMatcher()

    cand1 = TrackMetadata(title="Get Lucky", artist="Daft Punk", album="Random Access Memories", duration=248.0)
    cand2 = TrackMetadata(title="Get Lucky (Radio Edit)", artist="Daft Punk", album="Get Lucky", duration=240.0)
    cand3 = TrackMetadata(title="Lucky", artist="Jason Mraz", album="We Sing. We Dance.", duration=189.0)

    monkeypatch.setattr(matcher, "search_all", lambda q, **kwargs: [cand1, cand2, cand3])

    ranked = matcher.get_ranked_candidates(
        query="Daft Punk Get Lucky",
        expected_title="Get Lucky",
        expected_artist="Daft Punk",
        expected_duration=248.0,
    )

    assert len(ranked) >= 2
    # Top ranked candidate should be the exact match
    top_score, top_cand = ranked[0]
    assert top_cand.title == "Get Lucky"
    assert top_score >= 80.0
    assert ranked[0][0] >= ranked[1][0]


def test_pipeline_with_candidate_selector(tmp_path: Path, monkeypatch):
    library_dir = tmp_path / "music"
    inbox_dir = tmp_path / "inbox"
    temp_dir = tmp_path / "temp"
    for d in [library_dir, inbox_dir, temp_dir]:
        d.mkdir(parents=True)

    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=library_dir, inbox_dir=inbox_dir, temp_dir=temp_dir),
    )

    test_file = inbox_dir / "track.opus"
    # Create empty opus dummy
    test_file.write_bytes(b"dummy audio")

    pipeline = ProcessingPipeline(config)

    c1 = TrackMetadata(title="Track Option 1", artist="Artist A", album="Album 1")
    c2 = TrackMetadata(title="Track Option 2", artist="Artist B", album="Album 2")

    monkeypatch.setattr(pipeline.matcher, "get_ranked_candidates", lambda *args, **kwargs: [(90.0, c1), (80.0, c2)])
    monkeypatch.setattr(pipeline.lyrics_provider, "get_synced_lyrics", lambda *args, **kwargs: None)
    monkeypatch.setattr(pipeline, "convert_to_opus", lambda f: f)
    monkeypatch.setattr(pipeline.tagger, "tag_opus", lambda f, m: None)

    # Selector that picks second candidate
    def pick_second(candidates: List[Tuple[float, TrackMetadata]], query: str):
        return candidates[1][1]

    dest_audio, _, meta = pipeline.process_file(test_file, candidate_selector=pick_second)
    assert meta.title == "Track Option 2"
    assert meta.artist == "Artist B"
