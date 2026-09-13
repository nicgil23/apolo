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
    help="""[bold cyan]Apolo[/bold cyan] - Modern CLI Music Suite: Lossless/Hi-Fi to Opus Transcoder, Smart Metadata Tagger, Synced Lyrics Downloader & Library Organizer.

[bold yellow]Key Features:[/bold yellow]
  • [green]Audio/Video Transcoding[/green]: Converts any format (.flac, .mp3, .wav, .m4a, .mp4, .mkv, etc.) to consistent, acoustically transparent high-quality [bold].opus[/bold] (256k VBR).
  • [green]Metadata Tagging & Preservation[/green]: Preserves native tags and embedded cover art from pre-tagged sources (e.g. Soulseek), with automatic fallback to Deezer, iTunes, and MusicBrainz.
  • [green]Origin Tagging[/green]: Tracks track origins ([bold]ORIGIN / SOURCE[/bold]) automatically (e.g., YouTube, SoundCloud) or via CLI flags (e.g., [bold]--origin soulseek[/bold]).
  • [green]Synced Lyrics[/green]: Fetches and embeds timed synced LRC lyrics into the Opus container and sidecar files.
  • [green]Clean Library Structure[/green]: Organizes tracks neatly into Artist/Album folders, handles compilations, multi-disc sets, and single releases.""",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
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
    table.add_row("Disc Number", str(meta.disc_number or "-"))
    table.add_row("Disc Total", str(meta.disc_total or "-"))
    table.add_row("Release Date", str(meta.date or "-"))
    table.add_row("Genre", str(meta.genre or "-"))
    table.add_row("Origin / Source", str(meta.origin or "-"))
    table.add_row("Compilation", "Yes" if meta.compilation else "No")
    table.add_row("Cover Art", "Embedded (High Quality)" if meta.cover_art_data or meta.cover_art_url else "None")
    table.add_row("Synced Lyrics", "Embedded + Sidecar .lrc" if dest_lrc else ("Embedded" if meta.synced_lyrics else "Not found"))
    table.add_row("Destination", str(dest_audio))

    console.print(table)
    console.print()


@app.command(name="download")
@app.command(name="dl", hidden=True)
def download_cmd(
    urls: List[str] = typer.Argument(..., help="URLs from YouTube, SoundCloud, or supported extractors to download"),
    origin: Optional[str] = typer.Option(
        None,
        "--origin",
        "-o",
        help="Custom origin/source identifier (e.g. 'youtube', 'soundcloud'). Auto-detected by default.",
    ),
):
    """[bold green]Download[/bold green] tracks from YouTube / SoundCloud in high quality [bold].opus[/bold], fetch metadata/lyrics, tag origin, and organize into your library."""
    config = load_config()
    pipeline = ProcessingPipeline(config)

    for url in urls:
        console.print(f"\n[bold magenta]Processing URL:[/bold magenta] {url}")
        with console.status("[bold cyan]Working on audio download & tagging...[/bold cyan]") as status:
            def update_status(step: str, msg: str):
                status.update(f"[bold cyan]{msg}[/bold cyan]")

            try:
                results = pipeline.process_url(url, origin=origin, on_progress=update_status)
                if not results:
                    console.print(f"[bold red]Error: No audio could be processed for:[/bold red] {url}")
                for dest_audio, dest_lrc, meta in results:
                    display_track_summary(dest_audio, dest_lrc, meta)
            except Exception as e:
                console.print(f"[bold red]Error processing {url}:[/bold red] {e}")


@app.command(name="process")
@app.command(name="tag", hidden=True)
def process_cmd(
    paths: List[Path] = typer.Argument(
        ...,
        help="Path to audio/video file(s) or directories (e.g. Soulseek downloads, FLAC albums, MP3s, MP4s)",
    ),
    origin: Optional[str] = typer.Option(
        None,
        "--origin",
        "-o",
        help="Origin tag to assign (e.g. 'soulseek', 'bandcamp', 'cd_rip'). Preserves existing file tag if omitted.",
    ),
    force_rematch: bool = typer.Option(
        False,
        "--force-rematch",
        "-f",
        help="Force querying online providers (Deezer, iTunes, MusicBrainz) even if the file is already well-tagged.",
    ),
):
    """[bold green]Process and Tag[/bold green] existing audio or video files into high-quality [bold].opus[/bold], preserve valid metadata (Soulseek), tag origin, and organize into library."""
    config = load_config()
    pipeline = ProcessingPipeline(config)

    for path in paths:
        if not path.exists():
            console.print(f"[bold red]Path does not exist:[/bold red] {path}")
            continue

        if path.is_dir():
            console.print(f"\n[bold magenta]Scanning directory (recursive):[/bold magenta] {path}")
            with console.status("[bold cyan]Processing audio files...[/bold cyan]") as status:
                def update_status(step: str, msg: str):
                    status.update(f"[bold cyan]{msg}[/bold cyan]")

                results = pipeline.process_directory(path, origin=origin, force_rematch=force_rematch, on_progress=update_status)
                if not results:
                    console.print(f"[yellow]No supported audio/video files found in:[/yellow] {path}")
                for dest_audio, dest_lrc, meta in results:
                    display_track_summary(dest_audio, dest_lrc, meta)
        else:
            console.print(f"\n[bold magenta]Processing file:[/bold magenta] {path.name}")
            with console.status("[bold cyan]Processing audio file...[/bold cyan]") as status:
                def update_status(step: str, msg: str):
                    status.update(f"[bold cyan]{msg}[/bold cyan]")

                res = pipeline.process_file(path, origin=origin, force_rematch=force_rematch, on_progress=update_status)
                if res:
                    dest_audio, dest_lrc, meta = res
                    display_track_summary(dest_audio, dest_lrc, meta)
                else:
                    console.print(f"[bold yellow]Skipped or unsupported file:[/bold yellow] {path}")


@app.command(name="inbox")
def inbox_cmd(
    origin: Optional[str] = typer.Option(
        None,
        "--origin",
        "-o",
        help="Origin tag to assign to inbox tracks (defaults to config default_origin).",
    ),
    force_rematch: bool = typer.Option(
        False,
        "--force-rematch",
        "-f",
        help="Force online metadata rematching for inbox files even if already well-tagged.",
    ),
):
    """[bold green]Inbox Processor[/bold green]: Process and organize all audio/video files dropped into your configured Inbox directory."""
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

        results = pipeline.process_directory(inbox_dir, origin=origin, force_rematch=force_rematch, on_progress=update_status)
        if not results:
            console.print("[yellow]No audio files found in inbox.[/yellow]")
        for dest_audio, dest_lrc, meta in results:
            display_track_summary(dest_audio, dest_lrc, meta)


@app.command(name="reorganize")
@app.command(name="tidy", hidden=True)
def reorganize_cmd(
    paths: Optional[List[Path]] = typer.Argument(
        None,
        help="Path to audio file(s) or directories to reorganize (default: library_dir)",
    ),
):
    """[bold green]Reorganize[/bold green] existing music files in your library according to current folder rules and path templates."""
    config = load_config()
    pipeline = ProcessingPipeline(config)

    if paths:
        target_desc = ", ".join(str(p) for p in paths)
    else:
        target_desc = str(config.directories.library_dir)

    console.print(f"\n[bold magenta]Reorganizing:[/bold magenta] {target_desc}")
    with console.status("[bold cyan]Analyzing and relocating files...[/bold cyan]") as status:
        def update_status(step: str, msg: str):
            status.update(f"[bold cyan]{msg}[/bold cyan]")

        moved = pipeline.reorganize_paths(paths, on_progress=update_status)

    if not moved:
        console.print("[bold green]All files are already correctly organized.[/bold green]")
    else:
        table = Table(title=f"Reorganized Tracks ({len(moved)} moved)", show_header=True, header_style="bold cyan")
        table.add_column("Original Location", style="dim")
        table.add_column("New Organized Location", style="green")
        for old_p, new_p in moved:
            table.add_row(str(old_p), str(new_p))
        console.print(table)


@app.command(name="config")
def config_cmd():
    """[bold green]View Configuration[/bold green]: Show current Apolo configuration, directories, audio transcoding settings, and metadata providers."""
    config = load_config()
    config_path = get_config_path()

    panel_content = f"""[bold green]Config file:[/bold green] {config_path}

[bold cyan]Directories:[/bold cyan]
  - Library Dir:  {config.directories.library_dir}
  - Inbox Dir:    {config.directories.inbox_dir}
  - Temp Dir:     {config.directories.temp_dir}

[bold cyan]Organization:[/bold cyan]
  - Path Template:      {config.organization.path_template}
  - Multi-Disc Folder:  {config.organization.multi_disc_folder}
  - Various Artists:    {config.organization.various_artists_folder}
  - Group Singles:      {config.organization.group_singles}
  - Collision Strategy: {config.organization.collision_strategy}
  - Save .lrc file:     {config.organization.save_lrc_file}
  - Embed Cover Art:    {config.organization.embed_cover_art} (Max: {config.organization.max_cover_size}px)

[bold cyan]Transcoder & Downloader:[/bold cyan]
  - Codec:              {config.downloader.audio_format}
  - Bitrate:            {config.downloader.audio_bitrate} (Acoustically transparent VBR)
  - Default Origin:     {config.downloader.default_origin}
  - Preserve Tags:      {config.downloader.preserve_existing_tags} (Preserve Soulseek / Native metadata)

[bold cyan]Metadata & Lyrics Providers:[/bold cyan]
  - Deezer:             {config.providers.prefer_deezer}
  - iTunes:             {config.providers.prefer_itunes}
  - MusicBrainz:        {config.providers.prefer_musicbrainz}
  - Synced Only:        {config.providers.synced_lyrics_only}
"""
    console.print(Panel(panel_content, title="Apolo Configuration", border_style="bold blue"))


@app.command(name="info")
@app.command(name="inspect", hidden=True)
def info_cmd(
    paths: List[Path] = typer.Argument(
        ...,
        help="Path to audio/video file(s) or directories to inspect metadata, origin, cover art, and lyrics",
    ),
):
    """[bold green]Inspect Audio Metadata[/bold green]: View detailed metadata tags (Vorbis/ID3), origin, embedded cover art info, audio specs, and lyrics."""
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

