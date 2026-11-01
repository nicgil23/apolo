from pathlib import Path
from typing import List
import typer

from apolo.cli.ui import console
from apolo.constants import AUDIO_EXTENSIONS
from apolo.tagging.inspector import inspect_track


def register(app: typer.Typer) -> None:
    @app.command(name="info")
    @app.command(name="inspect", hidden=True)
    def info_cmd(
        paths: List[Path] = typer.Argument(
            ...,
            help="Path to audio/video file(s) or directories to inspect metadata, origin, cover art, and lyrics",
        ),
    ):
        """[bold green]Inspect Audio Metadata[/bold green]: View detailed metadata tags (Vorbis/ID3), origin, embedded cover art info, audio specs, and lyrics."""
        for path in paths:
            if path.is_file():
                inspect_track(path, console=console)
            elif path.is_dir():
                files = [p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS]
                if not files:
                    console.print(f"[yellow]No supported audio files in {path}[/yellow]")
                for f in sorted(files):
                    inspect_track(f, console=console)
            else:
                console.print(f"[bold red]File not found:[/bold red] {path}")
