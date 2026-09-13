import json
import threading
import time
from http import HTTPStatus
from unittest.mock import MagicMock, patch
import requests
import pytest

from apolo.metadata.models import TrackMetadata
from apolo.server import ApoloServer, ApoloTaskManager
from apolo.utils import clean_media_url


def test_clean_media_url_stripping():
    # YouTube Music radio mix URL
    dirty_ytm = "https://music.youtube.com/watch?v=VJGaVkDpWr4&list=RDAMVMVJGaVkDpWr4&start_radio=1"
    clean_ytm = clean_media_url(dirty_ytm)
    assert clean_ytm == "https://music.youtube.com/watch?v=VJGaVkDpWr4"

    # Standard YouTube with mix / extra params
    dirty_yt = "https://www.youtube.com/watch?v=5NV6Rdv1a3I&list=RD5NV6Rdv1a3I&index=3&t=20s"
    clean_yt = clean_media_url(dirty_yt)
    assert clean_yt == "https://www.youtube.com/watch?v=5NV6Rdv1a3I"

    # Explicit playlist preservation
    playlist_url = "https://www.youtube.com/playlist?list=PL123456789&si=abcdef"
    assert clean_media_url(playlist_url) == "https://www.youtube.com/playlist?list=PL123456789"


def test_task_manager_enqueue(tmp_path):
    tm = ApoloTaskManager()
    fake_meta = TrackMetadata(
        title="Test Song",
        artist="Test Artist",
        album="Test Album",
        date="2026",
    )
    with patch.object(tm.pipeline, "process_url", return_value=[(tmp_path / "song.opus", None, fake_meta)]):
        with patch.object(tm, "send_desktop_notification"):
            task = tm.enqueue_download("https://www.youtube.com/watch?v=12345&list=RD12345", origin="youtube")
            assert task.id is not None
            assert task.url == "https://www.youtube.com/watch?v=12345"
            assert task.status in ("queued", "downloading", "completed")

            time.sleep(0.5)
            finished_task = tm.get_task(task.id)
            assert finished_task is not None
            assert finished_task.status == "completed"
            assert len(finished_task.results) == 1
            assert finished_task.results[0]["title"] == "Test Song"


def test_task_manager_cancellation():
    tm = ApoloTaskManager()
    task = tm.enqueue_download("https://www.youtube.com/watch?v=dummy")
    assert tm.cancel_task(task.id) is True
    cancelled_task = tm.get_task(task.id)
    assert cancelled_task.status == "cancelled"
    assert cancelled_task.is_cancelled is True


def test_task_manager_failure():
    tm = ApoloTaskManager()
    with patch.object(tm.pipeline, "process_url", side_effect=RuntimeError("Download failed")):
        with patch.object(tm, "send_desktop_notification"):
            task = tm.enqueue_download("https://invalid-url.com")
            time.sleep(0.5)
            finished_task = tm.get_task(task.id)
            assert finished_task is not None
            assert finished_task.status == "failed"
            assert "Download failed" in (finished_task.error or "")


def test_server_http_endpoints(tmp_path):
    server = ApoloServer(host="127.0.0.1", port=45338)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.2)

    base_url = "http://127.0.0.1:45338"

    try:
        # Test GET /api/status
        res = requests.get(f"{base_url}/api/status")
        assert res.status_code == HTTPStatus.OK
        data = res.json()
        assert data["status"] == "ok"
        assert data["service"] == "apolo"
        assert "version" in data

        # Test CORS headers on OPTIONS
        options_res = requests.options(f"{base_url}/api/download")
        assert options_res.status_code == HTTPStatus.NO_CONTENT
        assert options_res.headers.get("Access-Control-Allow-Origin") == "*"

        # Test POST /api/download without body
        bad_res = requests.post(f"{base_url}/api/download", data="")
        assert bad_res.status_code == HTTPStatus.BAD_REQUEST

        # Test POST /api/download with valid URL and cancellation
        def mock_slow_process(*args, **kwargs):
            time.sleep(0.5)
            cancel_check = kwargs.get("cancel_check")
            if cancel_check and cancel_check():
                raise RuntimeError("Download cancelled by user")
            fake_meta = TrackMetadata(title="Sample Track", artist="Sample Artist", album="Single")
            return [(tmp_path / "sample.opus", None, fake_meta)]

        with patch.object(server.task_manager.pipeline, "process_url", side_effect=mock_slow_process):
            with patch.object(server.task_manager, "send_desktop_notification"):
                post_res = requests.post(
                    f"{base_url}/api/download",
                    json={"url": "https://www.youtube.com/watch?v=abcdef&list=RDabcdef", "origin": "youtube"},
                )
                assert post_res.status_code == HTTPStatus.ACCEPTED
                task_data = post_res.json()["task"]
                task_id = task_data["id"]
                assert task_data["url"] == "https://www.youtube.com/watch?v=abcdef"

                # Test POST /api/tasks/{task_id}/cancel while running
                cancel_res = requests.post(f"{base_url}/api/tasks/{task_id}/cancel")
                assert cancel_res.status_code == HTTPStatus.OK
                assert cancel_res.json()["status"] == "cancelled"

                # Test GET /api/tasks
                tasks_res = requests.get(f"{base_url}/api/tasks")
                assert tasks_res.status_code == HTTPStatus.OK
                tasks_list = tasks_res.json()["tasks"]
                assert any(t["id"] == task_id for t in tasks_list)

    finally:
        server.shutdown()
