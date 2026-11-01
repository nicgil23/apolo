from pathlib import Path
from typing import Optional
import typer
from rich.panel import Panel
from rich.table import Table

from apolo.cli.ui import console
from apolo.config import load_config, save_doctor_controlled_anomalies
from apolo.library.doctor import LibraryDoctor


def register(app: typer.Typer) -> None:
    @app.command(name="doctor")
    def doctor_cmd(
        library_dir: Optional[Path] = typer.Option(
            None,
            "--dir",
            "-d",
            help="Custom music library directory to audit (defaults to configured library_dir)",
        ),
        duplicates_only: bool = typer.Option(False, "--duplicates", help="Display duplicate tracks only"),
        missing_tracks_only: bool = typer.Option(False, "--missing-tracks", help="Display incomplete albums only"),
        controlled_only: bool = typer.Option(False, "--controlled", "--controlled-anomalies", help="Display controlled / intentional partial albums only"),
        missing_lyrics_only: bool = typer.Option(False, "--missing-lyrics", help="Display tracks missing synced lyrics only"),
        missing_covers_only: bool = typer.Option(False, "--missing-covers", help="Display tracks missing high-res covers only"),
        show_controlled: Optional[bool] = typer.Option(
            None,
            "--show-controlled/--no-show-controlled",
            "--show-anomalies/--no-show-anomalies",
            help="Show or hide detailed controlled anomalies table in general report (overrides doctor.show_controlled_anomalies)",
        ),
        show_missing_lyrics: Optional[bool] = typer.Option(
            None,
            "--show-lyrics/--no-show-lyrics",
            "--show-missing-lyrics/--no-show-missing-lyrics",
            help="Show or hide detailed missing synced lyrics table in general report (overrides doctor.show_missing_lyrics)",
        ),
        control_album: Optional[str] = typer.Option(None, "--control", help="Mark an album pattern as a controlled intentional partial album in config.toml (e.g. 'C.R.O - Malos Cantores')"),
        uncontrol_album: Optional[str] = typer.Option(None, "--uncontrol", help="Remove an album pattern from controlled anomalies in config.toml"),
        repair_lyrics: bool = typer.Option(False, "--repair-lyrics", help="Automatically fetch and embed missing synced lyrics from LRCLIB"),
        repair_covers: bool = typer.Option(False, "--repair-covers", help="Automatically fetch and embed missing high-res covers"),
        repair_fragmented: bool = typer.Option(False, "--repair-fragmented", help="Automatically unify fragmented collaborative artist folders"),
        fix_genres: bool = typer.Option(False, "--fix-genres", help="Audit, fetch missing genres from online providers / artist heuristics, and normalize genre tags across the library"),
        repair_all: bool = typer.Option(False, "--repair", "--repair-all", help="Run all repairs (lyrics, covers, fragmented folders, genres)"),
        dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview repairs without modifying files on disk"),
    ):
        """[bold green]Library Health & Diagnostics[/bold green]: Audit duplicates, incomplete albums, controlled partial albums, missing lyrics, and low-res covers with automated batch repairs."""
        config = load_config()

        # Handle --control / --uncontrol
        if control_album:
            current_list = list(config.doctor.controlled_anomalies)
            clean_pat = control_album.strip()
            if clean_pat and clean_pat not in current_list:
                current_list.append(clean_pat)
                save_doctor_controlled_anomalies(current_list)
                console.print(f"[bold green]Added controlled anomaly rule:[/bold green] '{clean_pat}' -> saved in config.toml")
            else:
                console.print(f"[yellow]Rule already exists or is empty:[/yellow] '{clean_pat}'")
            return

        if uncontrol_album:
            current_list = list(config.doctor.controlled_anomalies)
            clean_pat = uncontrol_album.strip()
            if clean_pat in current_list:
                current_list.remove(clean_pat)
                save_doctor_controlled_anomalies(current_list)
                console.print(f"[bold green]Removed controlled anomaly rule:[/bold green] '{clean_pat}' -> updated config.toml")
            else:
                console.print(f"[yellow]Rule not found in controlled anomalies:[/yellow] '{clean_pat}'")
            return

        doctor = LibraryDoctor(config)
        target_dir = library_dir or config.directories.library_dir

        console.print(f"\n[bold magenta]Auditing library health:[/bold magenta] {target_dir}")
        with console.status("[bold cyan]Scanning audio files and metadata...[/bold cyan]") as status:
            def update_status(step: str, msg: str):
                status.update(f"[bold cyan]{msg}[/bold cyan]")

            report = doctor.scan_library(library_dir=target_dir, on_progress=update_status)

        if report.total_tracks == 0:
            console.print(f"[yellow]No audio files found in {target_dir}[/yellow]")
            return

        # Handle batch repairs
        do_lyrics = repair_lyrics or repair_all
        do_covers = repair_covers or repair_all
        do_fragmented = repair_fragmented or repair_all
        do_genres = fix_genres or repair_all

        if do_fragmented:
            if not report.fragmented_artist_folders:
                console.print("[bold green]No fragmented artist folders found. No repair needed.[/bold green]")
            elif dry_run:
                console.print(f"[bold yellow][DRY-RUN] Would unify {len(report.fragmented_artist_folders)} fragmented artist folders into primary artist directories.[/bold yellow]")
            else:
                with console.status("[bold cyan]Unifying fragmented artist folders...[/bold cyan]") as status:
                    def update_status(step: str, msg: str):
                        status.update(f"[bold cyan]{msg}[/bold cyan]")
                    repaired = doctor.repair_fragmented_folders(report.fragmented_artist_folders, on_progress=update_status)
                console.print(f"[bold green]Unified {repaired} / {len(report.fragmented_artist_folders)} fragmented artist folders.[/bold green]")

        if do_lyrics:
            if not report.missing_lyrics:
                console.print("[bold green]All tracks already have lyrics. No repair needed.[/bold green]")
            elif dry_run:
                console.print(f"[bold yellow][DRY-RUN] Would fetch synced lyrics for {len(report.missing_lyrics)} tracks from LRCLIB.[/bold yellow]")
            else:
                with console.status("[bold cyan]Fetching missing lyrics from LRCLIB...[/bold cyan]") as status:
                    def update_status(step: str, msg: str):
                        status.update(f"[bold cyan]{msg}[/bold cyan]")
                    repaired = doctor.repair_lyrics(report.missing_lyrics, on_progress=update_status)
                console.print(f"[bold green]Repaired lyrics for {repaired} / {len(report.missing_lyrics)} tracks.[/bold green]")

        if do_covers:
            tracks_to_cover = [p for p, _ in report.missing_or_lowres_covers]
            if not tracks_to_cover:
                console.print("[bold green]All tracks have high-res cover art. No repair needed.[/bold green]")
            elif dry_run:
                console.print(f"[bold yellow][DRY-RUN] Would search high-res covers for {len(tracks_to_cover)} tracks.[/bold yellow]")
            else:
                with console.status("[bold cyan]Searching and embedding high-res covers...[/bold cyan]") as status:
                    def update_status(step: str, msg: str):
                        status.update(f"[bold cyan]{msg}[/bold cyan]")
                    repaired = doctor.repair_covers(tracks_to_cover, on_progress=update_status)
                console.print(f"[bold green]Embedded high-res covers for {repaired} / {len(tracks_to_cover)} tracks.[/bold green]")

        if do_genres:
            prefix = "[DRY-RUN] " if dry_run else ""
            with console.status(f"[bold cyan]{prefix}Auditing and normalizing library genres...[/bold cyan]") as status:
                def update_status(step: str, msg: str):
                    status.update(f"[bold cyan]{msg}[/bold cyan]")
                genre_res = doctor.fix_library_genres(library_dir=target_dir, dry_run=dry_run, on_progress=update_status)

            changes = genre_res["changes"]
            if not changes:
                console.print("[bold green]All track genres are already normalized. No repair needed.[/bold green]")
            else:
                header_style = "bold yellow" if dry_run else "bold cyan"
                title_text = f"[bold yellow]Genre Normalization (DRY-RUN: {genre_res['modified']} would update)[/bold yellow]" if dry_run else f"Genre Normalization ({genre_res['modified']} updated)"
                t = Table(title=title_text, show_header=True, header_style=header_style)
                t.add_column("Track", style="bold green")
                t.add_column("Artist", style="yellow")
                t.add_column("Old Genre", style="dim red")
                t.add_column("New Genre", style="bold cyan")
                t.add_column("Source", style="dim")

                for ch in changes[:50]:
                    t.add_row(ch["title"], ch["artist"], ch["old_genre"], ch["new_genre"], ch["source"])

                console.print(t)
                if len(changes) > 50:
                    console.print(f"[dim]...and {len(changes) - 50} more tracks.[/dim]")

                console.print(
                    f"[bold green]{prefix}Finished genre repair:[/bold green] {genre_res['modified']} updated, "
                    f"{genre_res['already_normalized']} already normalized, {genre_res['unresolved']} unresolved."
                )

        if do_lyrics or do_covers or do_fragmented or do_genres:
            return

        # Filter views if specific flags requested
        show_all = not any([duplicates_only, missing_tracks_only, controlled_only, missing_lyrics_only, missing_covers_only])

        # 1. Global Health Overview
        if show_all:
            score_color = "green" if report.health_score >= 85 else ("yellow" if report.health_score >= 60 else "red")
            lyrics_color = "green" if report.lyrics_coverage >= 80 else ("yellow" if report.lyrics_coverage >= 50 else "cyan")
            lyrics_count = report.total_tracks - len(report.missing_lyrics)
            summary_panel = f"""[bold cyan]Audited Directory:[/bold cyan] {target_dir}
[bold cyan]Total Tracks:[/bold cyan]      {report.total_tracks}
[bold cyan]Total Albums:[/bold cyan]      {report.total_albums}
[bold cyan]Health Score:[/bold cyan]      [{score_color} bold]{report.health_score}%[/{score_color} bold]
[bold cyan]Lyrics Coverage:[/bold cyan]   [{lyrics_color} bold]{report.lyrics_coverage}%[/{lyrics_color} bold] ({lyrics_count}/{report.total_tracks} tracks)

[bold yellow]Issues Found:[/bold yellow]
  • Duplicate Groups:        {len(report.duplicates)}
  • Incomplete Albums:       {len(report.incomplete_albums)}
  • Controlled Anomalies:    {len(report.controlled_incomplete_albums)} (intentional partial albums)
  • Fragmented Artist Dirs:  {len(report.fragmented_artist_folders)}
  • Missing Synced Lyrics:   {len(report.missing_lyrics)}
  • Missing/Low-Res Covers:  {len(report.missing_or_lowres_covers)}
  • Missing Essential Tags:  {len(report.missing_essential_tags)}"""
            console.print(Panel(summary_panel, title="Apolo Library Health Report", border_style=score_color))

        # 2. Fragmented Folders Table
        if show_all and report.fragmented_artist_folders:
            frag_table = Table(title=f"Fragmented Artist Folders ({len(report.fragmented_artist_folders)} folders)", show_header=True, header_style="bold yellow")
            frag_table.add_column("Fragmented Folder", style="bold yellow")
            frag_table.add_column("Target Primary Artist", style="green")
            for folder, _, prim_name in report.fragmented_artist_folders:
                frag_table.add_row(folder.name, prim_name)
            console.print(frag_table)

        # 3. Duplicates Table
        if (show_all or duplicates_only) and report.duplicates:
            dup_table = Table(title=f"Duplicate Tracks ({len(report.duplicates)} groups)", show_header=True, header_style="bold yellow")
            dup_table.add_column("Artist - Title", style="bold yellow")
            dup_table.add_column("Type", style="dim")
            dup_table.add_column("Locations", style="green")
            for dup in report.duplicates:
                paths_str = "\n".join(str(p) for p in dup.tracks)
                dup_table.add_row(f"{dup.artist} - {dup.title}", dup.match_type, paths_str)
            console.print(dup_table)

        # 4. Incomplete Albums Table
        if (show_all or missing_tracks_only) and report.incomplete_albums:
            alb_table = Table(title=f"Incomplete Albums ({len(report.incomplete_albums)} albums)", show_header=True, header_style="bold red")
            alb_table.add_column("Album Artist & Title", style="bold yellow")
            alb_table.add_column("Total", style="dim")
            alb_table.add_column("Present", style="green")
            alb_table.add_column("Missing Tracks", style="bold red")
            for alb in report.incomplete_albums:
                pres_str = ", ".join(str(n) for n in alb.present_tracks)
                miss_str = ", ".join(str(n) for n in alb.missing_tracks)
                alb_table.add_row(f"{alb.album_artist} - {alb.album_title}", str(alb.track_total), pres_str, miss_str)
            console.print(alb_table)

        # 4b. Controlled Anomalies Table
        should_show_controlled = False
        if controlled_only:
            should_show_controlled = True
        elif show_all:
            if show_controlled is not None:
                should_show_controlled = show_controlled
            else:
                should_show_controlled = config.doctor.show_controlled_anomalies

        if should_show_controlled and report.controlled_incomplete_albums:
            ctrl_table = Table(title=f"Controlled Anomalies / Álbumes Parciales Controlados ({len(report.controlled_incomplete_albums)} albums)", show_header=True, header_style="bold blue")
            ctrl_table.add_column("Album Artist & Title", style="bold cyan")
            ctrl_table.add_column("Total", style="dim")
            ctrl_table.add_column("Present Tracks", style="green")
            ctrl_table.add_column("Unincluded Tracks", style="dim cyan")
            for alb in report.controlled_incomplete_albums:
                pres_str = ", ".join(str(n) for n in alb.present_tracks)
                miss_str = ", ".join(str(n) for n in alb.missing_tracks)
                ctrl_table.add_row(f"{alb.album_artist} - {alb.album_title}", str(alb.track_total), pres_str, miss_str)
            console.print(ctrl_table)

        # 5. Missing Lyrics
        should_show_lyrics = False
        if missing_lyrics_only:
            should_show_lyrics = True
        elif show_all:
            if show_missing_lyrics is not None:
                should_show_lyrics = show_missing_lyrics
            else:
                should_show_lyrics = config.doctor.show_missing_lyrics

        if should_show_lyrics and report.missing_lyrics:
            lyr_table = Table(title=f"Tracks Missing Synced Lyrics ({len(report.missing_lyrics)} tracks)", show_header=True, header_style="bold cyan")
            lyr_table.add_column("File Path", style="cyan")
            for p in report.missing_lyrics[:15]:
                lyr_table.add_row(str(p))
            if len(report.missing_lyrics) > 15:
                lyr_table.add_row(f"[dim]... and {len(report.missing_lyrics) - 15} more (use --repair-lyrics to fetch)[/dim]")
            console.print(lyr_table)

        # 6. Missing / Low-Res Covers
        if (show_all or missing_covers_only) and report.missing_or_lowres_covers:
            cov_table = Table(title=f"Cover Art Issues ({len(report.missing_or_lowres_covers)} tracks)", show_header=True, header_style="bold magenta")
            cov_table.add_column("File Path", style="magenta")
            cov_table.add_column("Issue", style="yellow")
            for p, reason in report.missing_or_lowres_covers[:15]:
                cov_table.add_row(str(p), reason)
            if len(report.missing_or_lowres_covers) > 15:
                cov_table.add_row(f"[dim]... and {len(report.missing_or_lowres_covers) - 15} more (use --repair-covers to fix)[/dim]", "")
            console.print(cov_table)
