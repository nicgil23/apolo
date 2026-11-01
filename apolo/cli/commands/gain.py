from pathlib import Path
from typing import List
import typer
from rich.table import Table

from apolo.audio.gain import LoudnessScanner
from apolo.cli.ui import console
from apolo.config import load_config


def register(app: typer.Typer) -> None:
    @app.command(name="gain")
    def gain_cmd(
        paths: List[Path] = typer.Argument(
            ...,
            help="Audio file(s) or directories to analyze and tag with EBU R128 / ReplayGain",
        ),
        target_lufs: float = typer.Option(
            -18.0,
            "--target-lufs",
            "-t",
            help="Target integrated loudness in LUFS (-18.0 for Opus/ReplayGain 2.0, -23.0 for EBU R128 broadcast)",
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            "-n",
            help="Simulate loudness measurement without writing tags to files",
        ),
    ):
        """[bold green]EBU R128 & ReplayGain Normalizer[/bold green]: Measure track loudness and write standard R128_TRACK_GAIN and REPLAYGAIN tags."""
        config = load_config()
        scanner = LoudnessScanner(config)

        prefix = "[bold yellow][DRY-RUN][/bold yellow] " if dry_run else ""
        console.print(f"\n{prefix}[bold magenta]Analyzing audio loudness (Target: {target_lufs} LUFS)...[/bold magenta]")

        with console.status("[bold cyan]Running ffmpeg ebur128 loudness analysis...[/bold cyan]") as status:
            def update_status(step: str, msg: str):
                status.update(f"[bold cyan]{msg}[/bold cyan]")

            results = scanner.scan_and_tag_paths(paths, target_lufs=target_lufs, dry_run=dry_run, on_progress=update_status)

        if not results:
            console.print("[yellow]No audio files analyzed.[/yellow]")
            return

        title_text = f"[bold yellow]Loudness Analysis (DRY-RUN: {len(results)} files)[/bold yellow]" if dry_run else f"Loudness Analysis & R128 Tagging ({len(results)} files)"
        header_style = "bold yellow" if dry_run else "bold cyan"
        table = Table(title=title_text, show_header=True, header_style=header_style)
        table.add_column("File", style="bold yellow")
        table.add_column("Integrated", style="cyan")
        table.add_column("True Peak", style="dim")
        table.add_column("Calculated Gain", style="green")
        table.add_column("R128 Q7.8 Tag", style="magenta")

        for f, res in results:
            gain_str = f"{res.gain_db:+.2f} dB"
            table.add_row(
                f.name,
                f"{res.integrated_lufs:.1f} LUFS",
                f"{res.true_peak_db:.1f} dBFS",
                gain_str,
                str(res.r128_gain_q78),
            )

        console.print(table)
