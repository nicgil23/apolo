from pathlib import Path
from typing import List
import typer
from rich.table import Table

from apolo.audio.fingerprint import AcousticFingerprinter
from apolo.cli.ui import console, display_track_summary
from apolo.config import load_config
from apolo.constants import AUDIO_EXTENSIONS
from apolo.pipeline import ProcessingPipeline


def register(app: typer.Typer) -> None:
    @app.command(name="identify")
    def identify_cmd(
        paths: List[Path] = typer.Argument(
            ...,
            help="Audio file(s) or directories to identify via acoustic fingerprint (Chromaprint / AcoustID)",
        ),
        apply: bool = typer.Option(
            False,
            "--apply",
            "-a",
            help="Apply identified metadata, fetch synced lyrics, tag and organize into library.",
        ),
        keep_lossless: bool = typer.Option(
            False,
            "--keep-lossless",
            "--lossless",
            "-k",
            help="Preserve lossless FLAC files directly without converting to Opus.",
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            "-n",
            help="Simulate identification and destination without modifying files.",
        ),
    ):
        """[bold green]Acoustic Fingerprinter[/bold green]: Identify untagged audio files using Chromaprint waveform fingerprinting and AcoustID."""
        config = load_config()
        fingerprinter = AcousticFingerprinter(config)
        pipeline = ProcessingPipeline(config)

        if not AcousticFingerprinter.is_fpcalc_available():
            console.print("[bold red]Warning: 'fpcalc' (Chromaprint CLI) is not installed or not in PATH.[/bold red]")
            console.print("[yellow]Please install chromaprint (e.g. 'sudo pacman -S chromaprint' or 'sudo apt install libchromaprint-tools').[/yellow]\n")

        candidate_files = []
        for p in paths:
            if not p.exists():
                console.print(f"[bold red]Path does not exist:[/bold red] {p}")
                continue
            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS:
                candidate_files.append(p)
            elif p.is_dir():
                candidate_files.extend([f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS])

        if not candidate_files:
            console.print("[yellow]No audio files found to identify.[/yellow]")
            return

        table = Table(title=f"Acoustic Fingerprint Identification ({len(candidate_files)} files)", show_header=True, header_style="bold cyan")
        table.add_column("File", style="bold yellow")
        table.add_column("Duration", style="dim")
        table.add_column("Identified Title", style="bold green")
        table.add_column("Identified Artist", style="yellow")
        table.add_column("Album", style="magenta")
        table.add_column("AcoustID Track ID", style="dim")

        for f in candidate_files:
            duration, fp = fingerprinter.fingerprint_file(f)
            if not duration or not fp:
                table.add_row(f.name, "-", "[red]Fingerprint Failed / fpcalc missing[/red]", "-", "-", "-")
                continue

            results = fingerprinter.lookup_fingerprint(duration, fp)
            if not results:
                table.add_row(f.name, f"{duration:.1f}s", "[yellow]No AcoustID Match[/yellow]", "-", "-", "-")
                continue

            match = results[0]
            dur_str = f"{duration:.1f}s"
            table.add_row(
                f.name,
                dur_str,
                match.title,
                match.artist,
                match.album or "Single",
                match.source_id or "-",
            )

            if apply:
                console.print(f"\n[bold magenta]Applying identified metadata to:[/bold magenta] {f.name}")
                lyrics = pipeline.lyrics_provider.get_synced_lyrics(
                    track_name=match.title,
                    artist_name=match.artist,
                    album_name=match.album,
                    duration=duration,
                )
                match.synced_lyrics = lyrics
                match.origin = config.downloader.default_origin

                should_preserve_flac = f.suffix.lower() == ".flac" and (keep_lossless or config.downloader.preserve_lossless)
                ext = ".flac" if should_preserve_flac else ".opus"

                if dry_run:
                    dest_audio = pipeline.organizer.get_destination_path(match, extension=ext)
                    dest_lrc = dest_audio.with_suffix(".lrc") if (config.organization.save_lrc_file and match.synced_lyrics) else None
                    display_track_summary(dest_audio, dest_lrc, match, dry_run=True)
                else:
                    if should_preserve_flac:
                        pipeline.tagger.tag_flac(f, match)
                        dest_audio, dest_lrc = pipeline.organizer.organize_track(f, match, extension=".flac")
                    else:
                        opus_f = pipeline.convert_to_opus(f)
                        pipeline.tagger.tag_opus(opus_f, match)
                        dest_audio, dest_lrc = pipeline.organizer.organize_track(opus_f, match, extension=".opus")
                        if f != opus_f and f.exists():
                            f.unlink()
                    display_track_summary(dest_audio, dest_lrc, match, dry_run=False)

        console.print()
        console.print(table)
