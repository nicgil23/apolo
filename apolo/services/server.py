import json
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from apolo import __version__
from apolo.config import ApoloConfig, load_config
from apolo.pipeline import ProcessingPipeline
from apolo.utils import clean_media_url


@dataclass
class TaskInfo:
    id: str
    url: str
    origin: str
    status: str  # queued, downloading, retrying, completed, failed, cancelled
    created_at: float
    updated_at: float
    title: str | None = None
    is_playlist: bool = False
    total_tracks: int = 0
    completed_tracks: int = 0
    failed_tracks: int = 0
    current_track_index: int | None = None
    current_track_title: str | None = None
    current_track_artist: str | None = None
    current_track_progress: float = 0.0
    current_track_progress_text: str = ""
    progress: float = 0.0
    progress_text: str = ""
    subtracks: list[dict[str, Any]] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    retry_count: int = 0
    next_retry_at: float | None = None
    is_cancelled: bool = False


class ApoloTaskManager:
    def __init__(self, config: ApoloConfig | None = None, max_workers: int = 3):
        self.config = config or load_config()
        self.pipeline = ProcessingPipeline(self.config)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: dict[str, TaskInfo] = {}

    @staticmethod
    def send_desktop_notification(title: str, message: str, icon_path: Path | None = None) -> None:
        """Sends a desktop notification using notify-send if available."""
        cmd = ["notify-send", "-a", "Apolo", title, message]
        if icon_path and icon_path.exists():
            cmd.extend(["-i", str(icon_path)])
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except Exception:
            pass

    def enqueue_download(
        self, url: str, origin: str | None = None, title: str | None = None
    ) -> TaskInfo:
        cleaned = clean_media_url(url.strip())
        task_id = str(uuid.uuid4())[:8]
        inferred_origin = origin or ("youtube" if "youtu" in cleaned.lower() else "download")
        now = time.time()
        is_playlist = "list=" in cleaned or "/playlist" in cleaned or "/browse" in cleaned
        task = TaskInfo(
            id=task_id,
            url=cleaned,
            origin=inferred_origin,
            status="queued",
            title=title,
            is_playlist=is_playlist,
            created_at=now,
            updated_at=now,
        )
        self.tasks[task_id] = task

        self.executor.submit(self._run_download_task, task)
        return task

    def cancel_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        if not task:
            return False
        if task.status in ("completed", "failed", "cancelled"):
            return False
        task.is_cancelled = True
        task.status = "cancelled"
        task.updated_at = time.time()
        return True

    def clear_history(self) -> int:
        """Removes all tasks from memory and cancels active downloads."""
        count = len(self.tasks)
        for task in self.tasks.values():
            if task.status in ("queued", "downloading", "retrying"):
                task.is_cancelled = True
                task.status = "cancelled"
        self.tasks.clear()
        return count

    def _run_download_task(self, task: TaskInfo) -> None:
        if task.is_cancelled:
            return

        task.status = "downloading"
        task.updated_at = time.time()

        def cancel_chk() -> bool:
            return task.is_cancelled

        def on_playlist_init(
            title: str, total_tracks: int, subtracks_data: list[dict[str, Any]]
        ) -> None:
            if not task.is_cancelled:
                task.is_playlist = True
                task.title = title or task.title or "Playlist"
                task.total_tracks = total_tracks
                task.subtracks = subtracks_data
                task.updated_at = time.time()

        def on_subtrack_status(
            sub_id: str,
            status: str,
            error: str | None = None,
            retry_count: int = 0,
            next_retry_at: float | None = None,
        ) -> None:
            if not task.is_cancelled:
                for st in task.subtracks:
                    if st.get("id") == sub_id:
                        st["status"] = status
                        if error is not None:
                            st["error"] = error
                        if retry_count:
                            st["retry_count"] = retry_count
                        st["next_retry_at"] = next_retry_at
                        if status == "completed":
                            st["progress"] = 100.0
                            st["progress_text"] = "Listo"
                        elif status == "retrying":
                            st["progress_text"] = "Reintentando en 10s..."
                        elif status == "failed":
                            st["progress_text"] = "Error"
                        break
                task.completed_tracks = sum(
                    1 for st in task.subtracks if st.get("status") == "completed"
                )
                task.failed_tracks = sum(1 for st in task.subtracks if st.get("status") == "failed")
                task.updated_at = time.time()

        def on_subtrack_progress(sub_id: str, pct: float, text: str) -> None:
            if not task.is_cancelled:
                for st in task.subtracks:
                    if st.get("id") == sub_id:
                        st["progress"] = pct
                        st["progress_text"] = text
                        st["status"] = "downloading"
                        break
                task.updated_at = time.time()

        def on_active_track(
            idx: int, total: int, title: str, artist: str | None, pct: float, text: str
        ) -> None:
            if not task.is_cancelled:
                task.current_track_index = idx
                task.current_track_title = title
                task.current_track_artist = artist
                task.current_track_progress = pct
                task.current_track_progress_text = text
                task.updated_at = time.time()

        def on_track_title(title: str) -> None:
            if not task.is_cancelled:
                task.title = title
                task.updated_at = time.time()

        def progress_cb(pct: float, text: str) -> None:
            if not task.is_cancelled:
                task.progress = pct
                task.progress_text = text
                if "reintentando" in text.lower():
                    task.status = "retrying"
                elif task.status == "retrying" and "reintentando" not in text.lower():
                    task.status = "downloading"
                task.updated_at = time.time()

        try:
            processed = self.pipeline.process_url(
                task.url,
                origin=task.origin,
                suggested_title=task.title,
                progress_callback=progress_cb,
                cancel_check=cancel_chk,
                on_playlist_init=on_playlist_init,
                on_subtrack_status=on_subtrack_status,
                on_subtrack_progress=on_subtrack_progress,
                on_active_track=on_active_track,
                on_track_title=on_track_title,
            )

            if task.is_cancelled:
                task.status = "cancelled"
                task.updated_at = time.time()
                return

            task.results = []
            for dest_audio, dest_lrc, meta in processed:
                task.results.append(
                    {
                        "audio_path": str(dest_audio),
                        "lrc_path": str(dest_lrc) if dest_lrc else None,
                        "title": meta.title,
                        "artist": meta.artist,
                        "album": meta.album,
                        "date": meta.date,
                    }
                )
                self.send_desktop_notification(
                    title="Apolo: Canción añadida",
                    message=f"{meta.artist} - {meta.title}\n{meta.album or 'Single'}",
                )

            task.status = "completed"
            task.progress = 100.0
            task.progress_text = "100%"
            task.updated_at = time.time()
        except Exception as e:
            if task.is_cancelled or "cancelled" in str(e).lower():
                task.status = "cancelled"
                task.updated_at = time.time()
            else:
                task.status = "failed"
                task.error = str(e)
                task.updated_at = time.time()
                self.send_desktop_notification(
                    title="Apolo: Error",
                    message=f"Falló al procesar: {str(e)}",
                )

    def get_task(self, task_id: str) -> TaskInfo | None:
        return self.tasks.get(task_id)

    def list_tasks(self, limit: int = 20) -> list[TaskInfo]:
        all_tasks = sorted(self.tasks.values(), key=lambda t: t.created_at, reverse=True)
        return all_tasks[:limit]


class ApoloRequestHandler(BaseHTTPRequestHandler):
    task_manager: ApoloTaskManager

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Max-Age", "86400")

    def _send_json(self, data: Any, status: int = HTTPStatus.OK) -> None:
        content = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(content)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path in ("", "/health", "/api/status"):
            active_count = sum(
                1
                for t in self.task_manager.tasks.values()
                if t.status in ("queued", "downloading", "retrying")
            )
            self._send_json(
                {
                    "status": "ok",
                    "service": "apolo",
                    "version": __version__,
                    "active_tasks": active_count,
                    "total_tasks": len(self.task_manager.tasks),
                }
            )
            return

        if path == "/api/tasks":
            tasks = [asdict(t) for t in self.task_manager.list_tasks()]
            self._send_json({"tasks": tasks})
            return

        if path.startswith("/api/tasks/"):
            task_id = path.replace("/api/tasks/", "").strip()
            task = self.task_manager.get_task(task_id)
            if task:
                self._send_json(asdict(task))
            else:
                self._send_json({"error": "Task not found"}, status=HTTPStatus.NOT_FOUND)
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path in ("/api/tasks", "/api/tasks/clear"):
            cleared = self.task_manager.clear_history()
            self._send_json({"status": "ok", "cleared_count": cleared})
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path in ("/api/tasks/clear", "/api/tasks/clean"):
            cleared = self.task_manager.clear_history()
            self._send_json({"status": "ok", "cleared_count": cleared})
            return

        if path.startswith("/api/tasks/") and path.endswith("/cancel"):
            task_id = path.replace("/api/tasks/", "").replace("/cancel", "").strip()
            success = self.task_manager.cancel_task(task_id)
            if success:
                self._send_json({"status": "cancelled", "task_id": task_id})
            else:
                task = self.task_manager.get_task(task_id)
                if not task:
                    self._send_json({"error": "Task not found"}, status=HTTPStatus.NOT_FOUND)
                else:
                    self._send_json(
                        {"error": f"Cannot cancel task in status '{task.status}'"},
                        status=HTTPStatus.BAD_REQUEST,
                    )
            return

        if path == "/api/download":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                payload = json.loads(body) if body else {}
            except Exception as e:
                self._send_json(
                    {"error": f"Invalid JSON payload: {e}"}, status=HTTPStatus.BAD_REQUEST
                )
                return

            url = payload.get("url")
            if not url or not isinstance(url, str):
                self._send_json(
                    {"error": "Missing or invalid 'url' field"}, status=HTTPStatus.BAD_REQUEST
                )
                return

            origin = payload.get("origin")
            title = payload.get("title") or payload.get("suggested_title")
            task = self.task_manager.enqueue_download(url=url.strip(), origin=origin, title=title)
            self._send_json(
                {
                    "message": "Download task enqueued successfully",
                    "task": asdict(task),
                },
                status=HTTPStatus.ACCEPTED,
            )
            return

        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: Any) -> None:
        pass


class ApoloServer:
    def __init__(
        self, host: str = "127.0.0.1", port: int = 4533, config: ApoloConfig | None = None
    ):
        self.host = host
        self.port = port
        self.config = config or load_config()
        self.task_manager = ApoloTaskManager(self.config)

        class CustomHandler(ApoloRequestHandler):
            task_manager = self.task_manager

        self.server = ThreadingHTTPServer((self.host, self.port), CustomHandler)

    def serve_forever(self) -> None:
        self.server.serve_forever()

    def shutdown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.task_manager.executor.shutdown(wait=False)
