import threading
import time
from http import HTTPStatus
from unittest.mock import patch

import requests

from apolo.metadata.models import TrackMetadata
from apolo.services.server import ApoloServer, ApoloTaskManager
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
    with patch.object(
        tm.pipeline, "process_url", return_value=[(tmp_path / "song.opus", None, fake_meta)]
    ):
        with patch.object(tm, "send_desktop_notification"):
            task = tm.enqueue_download(
                "https://www.youtube.com/watch?v=12345&list=RD12345", origin="youtube"
            )
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
    with patch.object(tm, "_run_download_task"):
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

        with patch.object(
            server.task_manager.pipeline, "process_url", side_effect=mock_slow_process
        ):
            with patch.object(server.task_manager, "send_desktop_notification"):
                post_res = requests.post(
                    f"{base_url}/api/download",
                    json={
                        "url": "https://www.youtube.com/watch?v=abcdef&list=RDabcdef",
                        "origin": "youtube",
                    },
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

                # Test POST /api/tasks/clear
                clear_res = requests.post(f"{base_url}/api/tasks/clear")
                assert clear_res.status_code == HTTPStatus.OK
                assert clear_res.json()["status"] == "ok"
                assert clear_res.json()["cleared_count"] >= 1

    finally:
        server.shutdown()


def test_task_manager_clear_history():
    tm = ApoloTaskManager()
    with patch.object(tm, "_run_download_task"):
        t1 = tm.enqueue_download("https://www.youtube.com/watch?v=111")
        t2 = tm.enqueue_download("https://www.youtube.com/watch?v=222")
    t1.status = "completed"
    t2.status = "failed"
    cleared = tm.clear_history()
    assert cleared == 2
    assert len(tm.tasks) == 0


def test_task_manager_playlist_subtracks():
    tm = ApoloTaskManager()

    def mock_playlist_process(url, **kwargs):
        on_playlist_init = kwargs.get("on_playlist_init")
        on_subtrack_status = kwargs.get("on_subtrack_status")
        on_subtrack_progress = kwargs.get("on_subtrack_progress")
        if on_playlist_init:
            on_playlist_init(
                "Abbey Road",
                2,
                [
                    {"id": "t1", "title": "Come Together", "status": "queued", "progress": 0.0},
                    {"id": "t2", "title": "Something", "status": "queued", "progress": 0.0},
                ],
            )
        if on_subtrack_status:
            on_subtrack_status("t1", "downloading")
        if on_subtrack_progress:
            on_subtrack_progress("t1", 50.0, "50%")
        if on_subtrack_status:
            on_subtrack_status("t1", "completed")
            on_subtrack_status("t2", "completed")
        return []

    with patch.object(tm.pipeline, "process_url", side_effect=mock_playlist_process):
        task = tm.enqueue_download("https://www.youtube.com/playlist?list=PL123")
        time.sleep(0.4)
        t = tm.get_task(task.id)
        assert t.is_playlist is True
        assert t.title == "Abbey Road"
        assert t.total_tracks == 2
        assert t.subtracks[0]["status"] == "completed"


def test_enqueue_download_with_title():
    tm = ApoloTaskManager()
    with patch.object(tm, "_run_download_task"):
        task = tm.enqueue_download(
            "https://www.youtube.com/watch?v=xyz", origin="browser", title="Custom Song Title"
        )
        assert task.title == "Custom Song Title"


def test_task_active_track_callbacks():
    tm = ApoloTaskManager()

    def mock_process(url, **kwargs):
        on_active_track = kwargs.get("on_active_track")
        if on_active_track:
            on_active_track(1, 10, "First Track", "Artist", 45.0, "45%")
        return []

    with patch.object(tm.pipeline, "process_url", side_effect=mock_process):
        task = tm.enqueue_download("https://www.youtube.com/playlist?list=PLxyz")
        time.sleep(0.3)
        t = tm.get_task(task.id)
        assert t.current_track_index == 1
        assert t.current_track_title == "First Track"
        assert t.current_track_artist == "Artist"
        assert t.current_track_progress == 45.0
