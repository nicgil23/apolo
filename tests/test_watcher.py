import subprocess
from pathlib import Path
from unittest.mock import patch
import pytest
from typer.testing import CliRunner

from apolo.cli import app
from apolo.config import ApoloConfig, DirectoriesConfig
from apolo.metadata.models import TrackMetadata
from apolo.tagger import AudioTagger
from apolo.watcher import InboxWatcher


def create_dummy_opus(output_path: Path):
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
    meta = TrackMetadata(title="Inbox Song", artist="Inbox Artist")
    AudioTagger.tag_opus(output_path, meta)


def test_inbox_watcher_debounce_and_processing(tmp_path):
    inbox_dir = tmp_path / "Inbox"
    library_dir = tmp_path / "Library"
    config = ApoloConfig(directories=DirectoriesConfig(inbox_dir=inbox_dir, library_dir=library_dir))
    watcher = InboxWatcher(config)

    test_file = inbox_dir / "incoming.opus"
    create_dummy_opus(test_file)

    cache = {}
    # First poll: caches size, does not process yet (to ensure file write is finished)
    results_pass1 = watcher.scan_and_process_stable_files(inbox_dir, cache)
    assert len(results_pass1) == 0
    assert test_file in cache

    # Second poll: size is identical and stable -> processes file
    with patch.object(InboxWatcher, "send_desktop_notification"):
        results_pass2 = watcher.scan_and_process_stable_files(inbox_dir, cache)
        assert len(results_pass2) == 1
        dest_audio, dest_lrc, meta = results_pass2[0]
        assert dest_audio.exists()
        assert meta.title == "Inbox Song"


def test_watch_cli_once(tmp_path):
    runner = CliRunner()
    inbox_dir = tmp_path / "Inbox"
    inbox_dir.mkdir(parents=True, exist_ok=True)

    result = runner.invoke(app, ["watch", "--dir", str(inbox_dir), "--once"])
    assert result.exit_code == 0
