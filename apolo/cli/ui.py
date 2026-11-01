from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from apolo.metadata.models import TrackMetadata

console = Console()


def display_track_summary(
    dest_audio: Path, dest_lrc: Path | None, meta: TrackMetadata, dry_run: bool = False
) -> None:
    title_text = (
        "[bold yellow]Apolo Simulation (DRY-RUN - No files modified)[/bold yellow]"
        if dry_run
        else "Apolo Processed Track"
    )
    header_style = "bold yellow" if dry_run else "bold cyan"
    table = Table(title=title_text, show_header=True, header_style=header_style)
    table.add_column("Metadata Field", style="bold yellow")
    table.add_column("Value", style="yellow" if dry_run else "green")

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
    table.add_row(
        "Cover Art",
        "Embedded (High Quality)" if meta.cover_art_data or meta.cover_art_url else "None",
    )
    table.add_row(
        "Synced Lyrics",
        "Embedded + Sidecar .lrc"
        if dest_lrc
        else ("Embedded" if meta.synced_lyrics else "Not found"),
    )
    table.add_row("Destination" + (" (Simulated)" if dry_run else ""), str(dest_audio))

    console.print(table)
    console.print()


def make_cli_candidate_selector(matcher, console_instance):
    def selector(candidates: list[tuple[float, TrackMetadata]], query: str) -> TrackMetadata | None:
        curr_candidates = candidates
        curr_query = query
        while True:
            if not curr_candidates:
                console_instance.print(
                    f"[yellow]No candidates available for:[/yellow] {curr_query}"
                )
                return None

            table = Table(
                title=f"Metadata Candidates for: [bold yellow]{curr_query}[/bold yellow]",
                show_header=True,
                header_style="bold cyan",
            )
            table.add_column("#", style="bold yellow", justify="right")
            table.add_column("Score", style="cyan", justify="right")
            table.add_column("Title", style="bold green")
            table.add_column("Artist", style="yellow")
            table.add_column("Album", style="magenta")
            table.add_column("Year", style="dim")
            table.add_column("Source", style="dim")

            for i, (score, cand) in enumerate(curr_candidates, 1):
                table.add_row(
                    str(i),
                    f"{score:.0f}%",
                    cand.title,
                    cand.artist,
                    cand.album or "Single",
                    cand.get_year() or "-",
                    cand.provider_source or "web",
                )

            console_instance.print()
            console_instance.print(table)
            console_instance.print(
                "[dim]Options: [1-N] Select candidate | [0 / s] Skip / Use default metadata | [m] Manual search query[/dim]"
            )

            choice = typer.prompt("Select candidate", default="1").strip().lower()
            if choice in ["0", "s", "skip"]:
                return None
            if choice in ["m", "manual"]:
                new_q = typer.prompt("Enter new search query").strip()
                if new_q:
                    curr_query = new_q
                    curr_candidates = matcher.get_ranked_candidates(query=new_q, min_score=0.0)
                    continue
            try:
                idx = int(choice)
                if 1 <= idx <= len(curr_candidates):
                    return curr_candidates[idx - 1][1]
            except ValueError:
                pass
            console_instance.print("[red]Invalid selection. Try again.[/red]")

    return selector
