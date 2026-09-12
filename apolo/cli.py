import sys
from pathlib import Path
from typing import List, Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from apolo.config import get_config_path, load_config
from apolo.metadata.models import METADATOS_BIBLIOTECA, TrackMetadata
from apolo.pipeline import ProcessingPipeline

app = typer.Typer(
    name="apolo",
    help="Apolo - Music Downloader, Metadata Tagger, and Library Organizer.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def display_track_summary(dest_audio: Path, dest_lrc: Optional[Path], meta: TrackMetadata) -> None:
    table = Table(title="Apolo Processed Track", show_header=True, header_style="bold cyan")
    table.add_column("Metadata Field", style="bold yellow")
    table.add_column("Value", style="green")

    table.add_row("Title", meta.title)
    table.add_row("Artist", meta.artist)
    table.add_row("Album Artist", meta.album_artist or meta.artist)
    table.add_row("Album", meta.album or "Single")
    table.add_row("Track Number", str(meta.track_number or "-"))
    table.add_row("Track Total", str(meta.track_total or "-"))
    table.add_row("Release Date", str(meta.date or "-"))
    table.add_row("Genre", str(meta.genre or "-"))
    table.add_row("Disc Number", str(meta.disc_number or "-"))
    table.add_row("Cover Art", "Embedded (High Quality)" if meta.cover_art_data or meta.cover_art_url else "None")
    table.add_row("Synced Lyrics", "Embedded + Sidecar .lrc" if dest_lrc else ("Embedded" if meta.synced_lyrics else "Not found"))
    table.add_row("Destination", str(dest_audio))

    console.print(table)
    console.print()


@app.command(name="download")
@app.command(name="dl", hidden=True)
def download_cmd(
    urls: List[str] = typer.Argument(..., help="URLs from YouTube or SoundCloud to download"),
):
    """Download songs from YouTube / SoundCloud in high quality .opus, tag and organize."""
    config = load_config()
    pipeline = ProcessingPipeline(config)

    for url in urls:
        console.print(f"\n[bold magenta]Processing URL:[/bold magenta] {url}")
        with console.status("[bold cyan]Working on audio download & tagging...[/bold cyan]") as status:
            def update_status(step: str, msg: str):
                status.update(f"[bold cyan]{msg}[/bold cyan]")

            try:
                results = pipeline.process_url(url, on_progress=update_status)
                if not results:
                    console.print(f"[bold red]Error: No audio could be processed for:[/bold red] {url}")
                for dest_audio, dest_lrc, meta in results:
                    display_track_summary(dest_audio, dest_lrc, meta)
            except Exception as e:
                console.print(f"[bold red]Error processing {url}:[/bold red] {e}")


@app.command(name="process")
@app.command(name="tag", hidden=True)
def process_cmd(
    paths: List[Path] = typer.Argument(..., help="Path to audio file(s) or directories to tag and organize"),
):
    """Tag existing audio files, fetch synced lyrics, and organize into library."""
    config = load_config()
    pipeline = ProcessingPipeline(config)

    for path in paths:
        if not path.exists():
            console.print(f"[bold red]Path does not exist:[/bold red] {path}")
            continue

        if path.is_dir():
            console.print(f"\n[bold magenta]Scanning directory:[/bold magenta] {path}")
            with console.status("[bold cyan]Processing audio files...[/bold cyan]") as status:
                def update_status(step: str, msg: str):
                    status.update(f"[bold cyan]{msg}[/bold cyan]")

                results = pipeline.process_directory(path, on_progress=update_status)
                for dest_audio, dest_lrc, meta in results:
                    display_track_summary(dest_audio, dest_lrc, meta)
        else:
            console.print(f"\n[bold magenta]Processing file:[/bold magenta] {path.name}")
            with console.status("[bold cyan]Processing audio file...[/bold cyan]") as status:
                def update_status(step: str, msg: str):
                    status.update(f"[bold cyan]{msg}[/bold cyan]")

                res = pipeline.process_file(path, on_progress=update_status)
                if res:
                    dest_audio, dest_lrc, meta = res
                    display_track_summary(dest_audio, dest_lrc, meta)
                else:
                    console.print(f"[bold yellow]Skipped or unsupported file:[/bold yellow] {path}")


@app.command(name="inbox")
def inbox_cmd():
    """Process all audio files in your configured Inbox directory."""
    config = load_config()
    inbox_dir = config.directories.inbox_dir
    if not inbox_dir.exists():
        inbox_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"[bold yellow]Inbox directory was empty/created at {inbox_dir}[/bold yellow]")
        return

    pipeline = ProcessingPipeline(config)
    console.print(f"\n[bold magenta]Processing Inbox:[/bold magenta] {inbox_dir}")
    with console.status("[bold cyan]Processing inbox audio files...[/bold cyan]") as status:
        def update_status(step: str, msg: str):
            status.update(f"[bold cyan]{msg}[/bold cyan]")

        results = pipeline.process_directory(inbox_dir, on_progress=update_status)
        if not results:
            console.print("[yellow]No audio files found in inbox.[/yellow]")
        for dest_audio, dest_lrc, meta in results:
            display_track_summary(dest_audio, dest_lrc, meta)


@app.command(name="config")
def config_cmd():
    """Show current Apolo configuration."""
    config = load_config()
    config_path = get_config_path()

    panel_content = f"""[bold green]Config file:[/bold green] {config_path}

[bold cyan]Directories:[/bold cyan]
  - Library Dir:  {config.directories.library_dir}
  - Inbox Dir:    {config.directories.inbox_dir}
  - Temp Dir:     {config.directories.temp_dir}

[bold cyan]Organization:[/bold cyan]
  - Path Template:   {config.organization.path_template}
  - Save .lrc file:  {config.organization.save_lrc_file}
  - Embed Cover Art: {config.organization.embed_cover_art} (Max: {config.organization.max_cover_size}px)

[bold cyan]Downloader:[/bold cyan]
  - Codec:   {config.downloader.audio_format}
  - Quality: {config.downloader.audio_quality} (Best VBR)

[bold cyan]Metadata & Lyrics:[/bold cyan]
  - Deezer:       {config.providers.prefer_deezer}
  - iTunes:       {config.providers.prefer_itunes}
  - MusicBrainz:  {config.providers.prefer_musicbrainz}
  - Synced Only:  {config.providers.synced_lyrics_only}
"""
    console.print(Panel(panel_content, title="Apolo Configuration", border_style="bold blue"))


@app.command(name="info")
@app.command(name="inspect", hidden=True)
def info_cmd(
    paths: List[Path] = typer.Argument(..., help="Path to audio file(s) to inspect metadata"),
):
    """View detailed metadata, embedded cover art info, and lyrics of audio file(s)."""
    from apolo.inspector import inspect_track

    for path in paths:
        if path.is_file():
            inspect_track(path, console=console)
        elif path.is_dir():
            from apolo.pipeline import AUDIO_EXTENSIONS
            files = [p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS]
            if not files:
                console.print(f"[yellow]No supported audio files in {path}[/yellow]")
            for f in sorted(files):
                inspect_track(f, console=console)
        else:
            console.print(f"[bold red]File not found:[/bold red] {path}")


def main():
    app()


if __name__ == "__main__":
    main()
