from pathlib import Path
from typing import Optional
import typer

from apolo.cli.ui import console
from apolo.config import load_config
from apolo.services.watcher import InboxWatcher


def register(app: typer.Typer) -> None:
    @app.command(name="watch")
    @app.command(name="daemon", hidden=True)
    def watch_cmd(
        watch_dir: Optional[Path] = typer.Option(
            None,
            "--dir",
            "-d",
            help="Directory to monitor (defaults to config inbox_dir)",
        ),
        poll_interval: float = typer.Option(
            2.0,
            "--interval",
            "-i",
            help="Polling interval in seconds",
        ),
        once: bool = typer.Option(
            False,
            "--once",
            help="Run a single scan iteration and exit",
        ),
    ):
        """[bold green]Inbox Watcher Daemon[/bold green]: Monitor Inbox in the background, auto-transcode and organize new tracks, and send desktop notifications."""
        config = load_config()
        watcher = InboxWatcher(config)
        watcher.run_watch_loop(watch_dir=watch_dir, poll_interval=poll_interval, once=once, console=console)
