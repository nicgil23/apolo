from pathlib import Path
from typing import List, Optional
import typer
from rich.table import Table

from apolo.cli.ui import console
from apolo.config import load_config
from apolo.pipeline import ProcessingPipeline


def register(app: typer.Typer) -> None:
    @app.command(name="reorganize")
    @app.command(name="tidy", hidden=True)
    def reorganize_cmd(
        paths: Optional[List[Path]] = typer.Argument(
            None,
            help="Path to audio file(s) or directories to reorganize (default: library_dir)",
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            "-n",
            help="Simulate library reorganization without moving files on disk.",
        ),
    ):
        """[bold green]Reorganize[/bold green] existing music files in your library according to current folder rules and path templates."""
        config = load_config()
        pipeline = ProcessingPipeline(config)

        if paths:
            target_desc = ", ".join(str(p) for p in paths)
        else:
            target_desc = str(config.directories.library_dir)

        prefix = "[bold yellow][DRY-RUN][/bold yellow] " if dry_run else ""
        console.print(f"\n{prefix}[bold magenta]Reorganizing:[/bold magenta] {target_desc}")
        status_msg = "[bold yellow]Simulating path relocations...[/bold yellow]" if dry_run else "[bold cyan]Analyzing and relocating files...[/bold cyan]"
        with console.status(status_msg) as status:
            def update_status(step: str, msg: str):
                status.update(f"[bold cyan]{msg}[/bold cyan]")

            moved = pipeline.reorganize_paths(paths, dry_run=dry_run, on_progress=update_status)

        if not moved:
            console.print("[bold green]All files are already correctly organized.[/bold green]")
        else:
            title_text = f"[bold yellow]Reorganized Tracks (DRY-RUN: {len(moved)} would move)[/bold yellow]" if dry_run else f"Reorganized Tracks ({len(moved)} moved)"
            header_style = "bold yellow" if dry_run else "bold cyan"
            table = Table(title=title_text, show_header=True, header_style=header_style)
            table.add_column("Original Location", style="dim")
            table.add_column("New Organized Location", style="yellow" if dry_run else "green")
            for old_p, new_p in moved:
                table.add_row(str(old_p), str(new_p))
            console.print(table)
