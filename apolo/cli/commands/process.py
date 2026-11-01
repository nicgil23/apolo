from pathlib import Path

import typer

from apolo.cli.ui import console, display_track_summary, make_cli_candidate_selector
from apolo.config import load_config
from apolo.pipeline import ProcessingPipeline


def register(app: typer.Typer) -> None:
    @app.command(name="process")
    @app.command(name="tag", hidden=True)
    def process_cmd(
        paths: list[Path] = typer.Argument(
            ...,
            help="Path to audio/video file(s) or directories (e.g. Soulseek downloads, FLAC albums, MP3s, MP4s)",
        ),
        origin: str | None = typer.Option(
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
        interactive: bool = typer.Option(
            False,
            "--interactive",
            "-i",
            help="Interactively review and select candidate metadata from online providers.",
        ),
        keep_lossless: bool | None = typer.Option(
            None,
            "--keep-lossless/--no-keep-lossless",
            "--lossless/--no-lossless",
            "-k",
            help="Preserve lossless FLAC files directly without converting to Opus (overrides config).",
        ),
        to_opus: bool = typer.Option(
            False,
            "--to-opus",
            help="Force transcoding FLAC audio to Opus (shortcut for --no-keep-lossless).",
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            "-n",
            help="Simulate processing and tagging without modifying files or filesystem.",
        ),
    ):
        """[bold green]Process and Tag[/bold green] existing audio or video files into high-quality [bold].opus[/bold] (or FLAC if lossless), preserve valid metadata, tag origin, and organize into library."""
        config = load_config()
        if to_opus or keep_lossless is False:
            effective_lossless = False
        elif keep_lossless is True:
            effective_lossless = True
        else:
            effective_lossless = config.downloader.preserve_lossless

        pipeline = ProcessingPipeline(config)
        selector = make_cli_candidate_selector(pipeline.matcher, console) if interactive else None

        for path in paths:
            if not path.exists():
                console.print(f"[bold red]Path does not exist:[/bold red] {path}")
                continue

            prefix = "[bold yellow][DRY-RUN][/bold yellow] " if dry_run else ""
            if path.is_dir():
                console.print(
                    f"\n{prefix}[bold magenta]Scanning directory (recursive):[/bold magenta] {path}"
                )
                status_msg = (
                    "[bold yellow]Simulating directory scan...[/bold yellow]"
                    if dry_run
                    else "[bold cyan]Processing audio files...[/bold cyan]"
                )
                with console.status(status_msg) as status:

                    def update_status(step: str, msg: str):
                        status.update(f"[bold cyan]{msg}[/bold cyan]")

                    results = pipeline.process_directory(
                        path,
                        origin=origin,
                        force_rematch=force_rematch,
                        dry_run=dry_run,
                        preserve_lossless=effective_lossless,
                        candidate_selector=selector,
                        on_progress=update_status,
                    )
                    if not results:
                        console.print(
                            f"[yellow]No supported audio/video files found in:[/yellow] {path}"
                        )
                    for dest_audio, dest_lrc, meta in results:
                        display_track_summary(dest_audio, dest_lrc, meta, dry_run=dry_run)
            else:
                console.print(
                    f"\n{prefix}[bold magenta]Processing file:[/bold magenta] {path.name}"
                )
                status_msg = (
                    "[bold yellow]Simulating file processing...[/bold yellow]"
                    if dry_run
                    else "[bold cyan]Processing audio file...[/bold cyan]"
                )
                with console.status(status_msg) as status:

                    def update_status(step: str, msg: str):
                        status.update(f"[bold cyan]{msg}[/bold cyan]")

                    res = pipeline.process_file(
                        path,
                        origin=origin,
                        force_rematch=force_rematch,
                        dry_run=dry_run,
                        preserve_lossless=effective_lossless,
                        candidate_selector=selector,
                        on_progress=update_status,
                    )
                    if res:
                        dest_audio, dest_lrc, meta = res
                        display_track_summary(dest_audio, dest_lrc, meta, dry_run=dry_run)
                    else:
                        console.print(
                            f"[bold yellow]Skipped or unsupported file:[/bold yellow] {path}"
                        )

    @app.command(name="inbox")
    def inbox_cmd(
        origin: str | None = typer.Option(
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
        interactive: bool = typer.Option(
            False,
            "--interactive",
            "-i",
            help="Interactively review and select candidate metadata from online providers.",
        ),
        keep_lossless: bool | None = typer.Option(
            None,
            "--keep-lossless/--no-keep-lossless",
            "--lossless/--no-lossless",
            "-k",
            help="Preserve lossless FLAC files directly without converting to Opus (overrides config).",
        ),
        to_opus: bool = typer.Option(
            False,
            "--to-opus",
            help="Force transcoding FLAC audio to Opus (shortcut for --no-keep-lossless).",
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            "-n",
            help="Simulate inbox processing without converting or moving files.",
        ),
    ):
        """[bold green]Inbox Processor[/bold green]: Process and organize all audio/video files dropped into your configured Inbox directory."""
        config = load_config()
        if to_opus or keep_lossless is False:
            effective_lossless = False
        elif keep_lossless is True:
            effective_lossless = True
        else:
            effective_lossless = config.downloader.preserve_lossless

        inbox_dir = config.directories.inbox_dir
        if not inbox_dir.exists():
            if not dry_run:
                inbox_dir.mkdir(parents=True, exist_ok=True)
                console.print(
                    f"[bold yellow]Inbox directory was empty/created at {inbox_dir}[/bold yellow]"
                )
            else:
                console.print(
                    f"[bold yellow][DRY-RUN] Inbox directory does not exist yet at {inbox_dir}[/bold yellow]"
                )
            return

        pipeline = ProcessingPipeline(config)
        selector = make_cli_candidate_selector(pipeline.matcher, console) if interactive else None
        prefix = "[bold yellow][DRY-RUN][/bold yellow] " if dry_run else ""
        console.print(f"\n{prefix}[bold magenta]Processing Inbox:[/bold magenta] {inbox_dir}")
        status_msg = (
            "[bold yellow]Simulating inbox audio files...[/bold yellow]"
            if dry_run
            else "[bold cyan]Processing inbox audio files...[/bold cyan]"
        )
        with console.status(status_msg) as status:

            def update_status(step: str, msg: str):
                status.update(f"[bold cyan]{msg}[/bold cyan]")

            results = pipeline.process_directory(
                inbox_dir,
                origin=origin,
                force_rematch=force_rematch,
                dry_run=dry_run,
                preserve_lossless=effective_lossless,
                candidate_selector=selector,
                on_progress=update_status,
            )
            if not results:
                console.print("[yellow]No audio files found in inbox.[/yellow]")
            for dest_audio, dest_lrc, meta in results:
                display_track_summary(dest_audio, dest_lrc, meta, dry_run=dry_run)
