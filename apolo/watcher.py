import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional
from rich.console import Console

from apolo.config import ApoloConfig, load_config
from apolo.pipeline import AUDIO_EXTENSIONS, ProcessingPipeline


class InboxWatcher:
    def __init__(self, config: Optional[ApoloConfig] = None):
        self.config = config or load_config()
        self.pipeline = ProcessingPipeline(self.config)
        self.inbox_dir = self.config.directories.inbox_dir

    @staticmethod
    def send_desktop_notification(title: str, message: str, icon_path: Optional[Path] = None) -> None:
        """Sends a Linux desktop notification using notify-send if available."""
        cmd = ["notify-send", "-a", "Apolo", title, message]
        if icon_path and icon_path.exists():
            cmd.extend(["-i", str(icon_path)])
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except Exception:
            pass

    def scan_and_process_stable_files(
        self,
        watch_dir: Path,
        file_size_cache: Dict[Path, int],
        on_event: Optional[Callable[[str, str], None]] = None,
    ) -> List[Tuple[Path, Optional[Path], any]]:
        """
        Scans watch_dir, checks file size stability across polls to debounce active writes,
        and processes stabilized audio files.
        """
        if not watch_dir.exists():
            return []

        candidates = [p for p in watch_dir.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS]
        current_paths = set(candidates)
        processed_results = []

        # Remove deleted files from cache
        for cached_p in list(file_size_cache.keys()):
            if cached_p not in current_paths:
                del file_size_cache[cached_p]

        for file_path in candidates:
            try:
                current_size = file_path.stat().st_size
            except Exception:
                continue

            last_size = file_size_cache.get(file_path)

            # If file size is stable between consecutive polls, it's ready to process
            if last_size is not None and last_size == current_size and current_size > 0:
                if on_event:
                    on_event("processing", f"Processing stabilized file: {file_path.name}")

                res = self.pipeline.process_file(file_path)
                if res:
                    dest_audio, dest_lrc, meta = res
                    processed_results.append((dest_audio, dest_lrc, meta))
                    # Desktop notification
                    self.send_desktop_notification(
                        title="Apolo Track Added",
                        message=f"{meta.artist} - {meta.title}\n{meta.album or 'Single'}",
                    )
                    if on_event:
                        on_event("completed", f"Organized: {meta.artist} - {meta.title}")

                if file_path in file_size_cache:
                    del file_size_cache[file_path]
            else:
                # Still writing or first seen
                file_size_cache[file_path] = current_size

        return processed_results

    def run_watch_loop(
        self,
        watch_dir: Optional[Path] = None,
        poll_interval: float = 2.0,
        once: bool = False,
        console: Optional[Console] = None,
    ) -> None:
        target_dir = watch_dir or self.inbox_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        file_size_cache: Dict[Path, int] = {}

        if console:
            console.print(f"[bold green]Apolo Watcher active:[/bold green] Monitoring [cyan]{target_dir}[/cyan] (Press Ctrl+C to stop)")

        try:
            while True:
                def event_callback(step: str, msg: str):
                    if console:
                        console.print(f"[bold cyan][{step.upper()}][/bold cyan] {msg}")

                self.scan_and_process_stable_files(target_dir, file_size_cache, on_event=event_callback)

                if once:
                    break

                time.sleep(poll_interval)
        except KeyboardInterrupt:
            if console:
                console.print("\n[yellow]Apolo Watcher stopped by user.[/yellow]")
