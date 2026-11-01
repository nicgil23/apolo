from pathlib import Path
from typing import List, Optional
import typer
from rich.table import Table

from apolo.cli.ui import console
from apolo.config import load_config
from apolo.library.playlists import PlaylistManager


def register(app: typer.Typer) -> None:
    playlist_app = typer.Typer(
        name="playlist",
        help="""[bold green]Playlist Management[/bold green]: Create smart M3U8 playlists by genre/year/artist, repair broken links, and export for DAPs/USB.""",
        no_args_is_help=True,
        rich_markup_mode="rich",
    )
    app.add_typer(playlist_app, name="playlist")

    @playlist_app.command(name="list")
    def playlist_list_cmd():
        """[bold green]List Playlists[/bold green]: Show all existing .m3u8 playlists in your library with track counts and link integrity."""
        config = load_config()
        pm = PlaylistManager(config)
        playlists = pm.list_playlists()

        if not playlists:
            console.print(f"[yellow]No playlists found in {pm.playlists_dir}[/yellow]")
            return

        table = Table(title=f"Apolo Playlists ({len(playlists)} found)", show_header=True, header_style="bold cyan")
        table.add_column("Playlist Name", style="bold yellow")
        table.add_column("Tracks (Valid / Total)", style="green")
        table.add_column("Duration", style="cyan")
        table.add_column("Status", style="magenta")

        for pl in playlists:
            status = "[green]All links OK[/green]" if pl.broken_tracks == 0 else f"[red]{pl.broken_tracks} broken links[/red]"
            table.add_row(pl.name, f"{pl.valid_tracks} / {pl.total_tracks}", pl.formatted_duration, status)

        console.print(table)

    @playlist_app.command(name="create")
    def playlist_create_cmd(
        name: str = typer.Argument(..., help="Playlist name (e.g. 'Synthwave Classics')"),
        paths: Optional[List[Path]] = typer.Argument(None, help="Audio files or directories to include in manual playlist"),
        genre: Optional[str] = typer.Option(None, "--genre", "-g", help="Filter tracks by genre (e.g. 'Synthwave')"),
        year: Optional[str] = typer.Option(None, "--year", "-y", help="Filter tracks by year or range (e.g. '1984' or '1980..1989')"),
        artist: Optional[str] = typer.Option(None, "--artist", "-a", help="Filter tracks by artist name"),
        origin: Optional[str] = typer.Option(None, "--origin", "-o", help="Filter tracks by origin tag (e.g. 'soulseek', 'youtube')"),
        compilation: Optional[bool] = typer.Option(None, "--compilation", "-c", help="Filter compilation tracks (true/false)"),
    ):
        """[bold green]Create Playlist[/bold green]: Create a smart M3U8 playlist dynamically filtered by genre/year/artist, or from specific paths."""
        config = load_config()
        pm = PlaylistManager(config)

        if paths:
            pl_path, count = pm.create_manual_playlist(name, paths)
        else:
            pl_path, count = pm.create_smart_playlist(
                name=name,
                genre=genre,
                year=year,
                artist=artist,
                origin=origin,
                compilation=compilation,
            )

        if count == 0:
            console.print(f"[yellow]Warning: Created empty playlist (0 tracks matched):[/yellow] {pl_path}")
        else:
            console.print(f"[bold green]Created playlist:[/bold green] {pl_path.name} [cyan]({count} tracks)[/cyan]")
            console.print(f"[dim]{pl_path}[/dim]")

    @playlist_app.command(name="repair")
    def playlist_repair_cmd():
        """[bold green]Repair Playlists[/bold green]: Relink broken file paths in all .m3u8 playlists after library reorganizations."""
        config = load_config()
        pm = PlaylistManager(config)
        console.print("\n[bold magenta]Scanning playlists for broken file paths...[/bold magenta]")

        repaired = pm.repair_playlists()
        if not repaired:
            console.print("[bold green]All playlist paths are intact. No repairs needed.[/bold green]")
        else:
            table = Table(title="Repaired Playlists", show_header=True, header_style="bold cyan")
            table.add_column("Playlist", style="bold yellow")
            table.add_column("Repaired Links", style="green")
            for pl_name, count in repaired.items():
                table.add_row(pl_name, f"{count} broken links relinked")
            console.print(table)

    @playlist_app.command(name="export")
    def playlist_export_cmd(
        name: str = typer.Argument(..., help="Playlist name to export (e.g. 'Roadtrip')"),
        dest: Path = typer.Argument(..., help="Destination directory (e.g. /media/usb/Music)"),
        copy_audio: bool = typer.Option(True, "--copy/--no-copy", help="Copy audio files to destination directory"),
    ):
        """[bold green]Export Playlist[/bold green]: Copy tracks and export adjusted .m3u8 playlist to an external device (DAP, USB, SD card)."""
        config = load_config()
        pm = PlaylistManager(config)
        try:
            exported_pl, count = pm.export_playlist(name, dest, copy_files=copy_audio)
            console.print(f"[bold green]Exported playlist successfully:[/bold green] {exported_pl.name} [cyan]({count} tracks)[/cyan]")
            console.print(f"[dim]Destination: {dest}[/dim]")
        except Exception as e:
            console.print(f"[bold red]Error exporting playlist:[/bold red] {e}")
            raise typer.Exit(code=1)
