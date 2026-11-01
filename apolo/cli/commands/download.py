from typing import List, Optional
import typer

from apolo.cli.ui import console, display_track_summary, make_cli_candidate_selector
from apolo.config import load_config
from apolo.pipeline import ProcessingPipeline


def register(app: typer.Typer) -> None:
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
        interactive: bool = typer.Option(
            False,
            "--interactive",
            "-i",
            help="Interactively review and select candidate metadata from online providers.",
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            "-n",
            help="Simulate download and tagging without modifying library files.",
        ),
    ):
        """[bold green]Download[/bold green] tracks from YouTube / SoundCloud in high quality [bold].opus[/bold], fetch metadata/lyrics, tag origin, and organize into your library."""
        config = load_config()
        pipeline = ProcessingPipeline(config)
        selector = make_cli_candidate_selector(pipeline.matcher, console) if interactive else None

        for url in urls:
            prefix = "[bold yellow][DRY-RUN][/bold yellow] " if dry_run else ""
            console.print(f"\n{prefix}[bold magenta]Processing URL:[/bold magenta] {url}")
            status_msg = "[bold yellow]Simulating download & metadata lookup...[/bold yellow]" if dry_run else "[bold cyan]Working on audio download & tagging...[/bold cyan]"
            with console.status(status_msg) as status:
                def update_status(step: str, msg: str):
                    status.update(f"[bold cyan]{msg}[/bold cyan]")

                try:
                    results = pipeline.process_url(
                        url,
                        origin=origin,
                        dry_run=dry_run,
                        candidate_selector=selector,
                        on_progress=update_status,
                    )
                    if not results:
                        console.print(f"[bold red]Error: No audio could be processed for:[/bold red] {url}")
                    for dest_audio, dest_lrc, meta in results:
                        display_track_summary(dest_audio, dest_lrc, meta, dry_run=dry_run)
                except Exception as e:
                    console.print(f"[bold red]Error processing {url}:[/bold red] {e}")
