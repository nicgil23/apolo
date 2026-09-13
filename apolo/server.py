import json
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
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
    status: str  # queued, downloading, completed, failed, cancelled
    created_at: float
    updated_at: float
    progress: float = 0.0
    progress_text: str = ""
    results: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    is_cancelled: bool = False


class ApoloTaskManager:
    def __init__(self, config: Optional[ApoloConfig] = None, max_workers: int = 3):
        self.config = config or load_config()
        self.pipeline = ProcessingPipeline(self.config)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: Dict[str, TaskInfo] = {}

    @staticmethod
    def send_desktop_notification(title: str, message: str, icon_path: Optional[Path] = None) -> None:
        """Sends a desktop notification using notify-send if available."""
        cmd = ["notify-send", "-a", "Apolo", title, message]
        if icon_path and icon_path.exists():
            cmd.extend(["-i", str(icon_path)])
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except Exception:
            pass

    def enqueue_download(self, url: str, origin: Optional[str] = None) -> TaskInfo:
        cleaned = clean_media_url(url.strip())
        task_id = str(uuid.uuid4())[:8]
        inferred_origin = origin or ("youtube" if "youtu" in cleaned.lower() else "download")
        now = time.time()
        task = TaskInfo(
            id=task_id,
            url=cleaned,
            origin=inferred_origin,
            status="queued",
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

    def _run_download_task(self, task: TaskInfo) -> None:
        if task.is_cancelled:
            return

        task.status = "downloading"
        task.updated_at = time.time()

        def progress_cb(pct: float, text: str):
            if not task.is_cancelled:
                task.progress = pct
                task.progress_text = text
                task.updated_at = time.time()

        def cancel_chk() -> bool:
            return task.is_cancelled

        try:
            processed = self.pipeline.process_url(
                task.url,
                origin=task.origin,
                progress_callback=progress_cb,
                cancel_check=cancel_chk,
            )

            if task.is_cancelled:
                task.status = "cancelled"
                task.updated_at = time.time()
                return

            task.results = []
            for dest_audio, dest_lrc, meta in processed:
                task.results.append({
                    "audio_path": str(dest_audio),
                    "lrc_path": str(dest_lrc) if dest_lrc else None,
                    "title": meta.title,
                    "artist": meta.artist,
                    "album": meta.album,
                    "date": meta.date,
                })
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

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        return self.tasks.get(task_id)

    def list_tasks(self, limit: int = 20) -> List[TaskInfo]:
        all_tasks = sorted(self.tasks.values(), key=lambda t: t.created_at, reverse=True)
        return all_tasks[:limit]


class ApoloRequestHandler(BaseHTTPRequestHandler):
    task_manager: ApoloTaskManager

    def _send_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
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
            active_count = sum(1 for t in self.task_manager.tasks.values() if t.status in ("queued", "downloading"))
            self._send_json({
                "status": "ok",
                "service": "apolo",
                "version": __version__,
                "active_tasks": active_count,
                "total_tasks": len(self.task_manager.tasks),
            })
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

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

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
                    self._send_json({"error": f"Cannot cancel task in status '{task.status}'"}, status=HTTPStatus.BAD_REQUEST)
            return

        if path == "/api/download":
            try:
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8")
                payload = json.loads(body) if body else {}
            except Exception as e:
                self._send_json({"error": f"Invalid JSON payload: {e}"}, status=HTTPStatus.BAD_REQUEST)
                return

            url = payload.get("url")
            if not url or not isinstance(url, str):
                self._send_json({"error": "Missing or invalid 'url' field"}, status=HTTPStatus.BAD_REQUEST)
                return

            origin = payload.get("origin")
            task = self.task_manager.enqueue_download(url=url.strip(), origin=origin)
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
    def __init__(self, host: str = "127.0.0.1", port: int = 4533, config: Optional[ApoloConfig] = None):
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
