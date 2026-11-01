import re
from pathlib import Path

import typer
from rich.table import Table

from apolo.cli.ui import console
from apolo.config import load_config
from apolo.constants import AUDIO_EXTENSIONS
from apolo.pipeline import ProcessingPipeline
from apolo.tagging.tagger import AudioTagger


def register(app: typer.Typer) -> None:
    @app.command(name="set")
    def set_cmd(
        paths: list[Path] = typer.Argument(
            ...,
            help="Path to audio file(s) or directories to update tags",
        ),
        title: str | None = typer.Option(None, "--title", "-t", help="Track title"),
        artist: str | None = typer.Option(None, "--artist", "-a", help="Artist name"),
        album_artist: str | None = typer.Option(
            None, "--album-artist", "-A", help="Album artist name"
        ),
        album: str | None = typer.Option(None, "--album", "-b", help="Album name"),
        track_number: int | None = typer.Option(None, "--track", "-n", help="Track number"),
        track_total: int | None = typer.Option(
            None, "--track-total", "-N", help="Total track count"
        ),
        disc_number: int | None = typer.Option(None, "--disc", "-d", help="Disc number"),
        disc_total: int | None = typer.Option(None, "--disc-total", "-D", help="Total disc count"),
        date: str | None = typer.Option(
            None, "--year", "--date", "-y", help="Release year or date (YYYY or YYYY-MM-DD)"
        ),
        genre: str | None = typer.Option(None, "--genre", "-g", help="Music genre"),
        origin: str | None = typer.Option(
            None, "--origin", "-o", help="Origin / source identifier"
        ),
        compilation: bool | None = typer.Option(
            None, "--compilation", "-c", help="Mark as compilation (true/false)"
        ),
        controlled_anomaly: bool | None = typer.Option(
            None,
            "--control / --no-control",
            "--controlled-anomaly / --no-controlled-anomaly",
            help="Mark or unmark track as controlled intentional partial album",
        ),
        lyrics: str | None = typer.Option(
            None, "--lyrics", "-l", help="Lyrics text or path to .lrc / .txt file"
        ),
        cover: Path | None = typer.Option(
            None, "--cover", help="Path to cover art image file to embed"
        ),
        reorganize: bool = typer.Option(
            False,
            "--reorganize",
            "-r",
            help="Automatically relocate files according to updated metadata",
        ),
        dry_run: bool = typer.Option(
            False, "--dry-run", "-n", help="Preview tag changes without writing to disk"
        ),
    ):
        """[bold green]Set Track Metadata[/bold green]: Modify specific metadata tags, lyrics, or cover art on audio files without wiping other tags."""
        # Validate cover art file
        cover_bytes = None
        if cover:
            if not cover.exists() or not cover.is_file():
                console.print(f"[bold red]Cover art file not found:[/bold red] {cover}")
                raise typer.Exit(code=1)
            cover_bytes = cover.read_bytes()

        # Read lyrics from file if path is given
        lyrics_content = lyrics
        if lyrics:
            lyrics_path = Path(lyrics)
            if lyrics_path.exists() and lyrics_path.is_file():
                try:
                    lyrics_content = lyrics_path.read_text(encoding="utf-8")
                except Exception:
                    pass

        # Build updates dictionary
        updates = {}
        if title is not None:
            updates["title"] = title
        if artist is not None:
            updates["artist"] = artist
        if album_artist is not None:
            updates["album_artist"] = album_artist
        if album is not None:
            updates["album"] = album
        if track_number is not None:
            updates["track_number"] = track_number
        if track_total is not None:
            updates["track_total"] = track_total
        if disc_number is not None:
            updates["disc_number"] = disc_number
        if disc_total is not None:
            updates["disc_total"] = disc_total
        if date is not None:
            updates["date"] = date
        if genre is not None:
            updates["genre"] = genre
        if origin is not None:
            updates["origin"] = origin
        if compilation is not None:
            updates["compilation"] = compilation
        if controlled_anomaly is not None:
            updates["controlled_anomaly"] = controlled_anomaly
            updates["partial_album"] = controlled_anomaly
        if lyrics_content is not None:
            updates["lyrics"] = lyrics_content

        if not updates and not cover_bytes:
            console.print(
                "[yellow]No tags or cover art specified to update. Use --help to view available options.[/yellow]"
            )
            return

        # Find target files
        target_files: list[Path] = []
        for p in paths:
            if not p.exists():
                console.print(f"[bold red]Path does not exist:[/bold red] {p}")
                continue
            if p.is_file():
                if p.suffix.lower() in AUDIO_EXTENSIONS:
                    target_files.append(p)
            elif p.is_dir():
                target_files.extend(
                    [
                        f
                        for f in p.rglob("*")
                        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
                    ]
                )

        target_files = sorted(list(set(target_files)))
        if not target_files:
            console.print("[yellow]No audio files found to update.[/yellow]")
            return

        config = load_config()
        pipeline = ProcessingPipeline(config)

        for file_path in target_files:
            info = pipeline.extract_file_info(file_path)
            table_title = (
                f"[bold yellow]Set Tags (DRY-RUN): {file_path.name}[/bold yellow]"
                if dry_run
                else f"Set Tags: {file_path.name}"
            )
            table = Table(
                title=table_title,
                show_header=True,
                header_style="bold yellow" if dry_run else "bold cyan",
            )
            table.add_column("Tag", style="bold yellow")
            table.add_column("Current Value", style="dim")
            table.add_column("New Value", style="yellow" if dry_run else "green")

            for k, v in updates.items():
                curr_val = str(info.get(k, "-") or "-")
                table.add_row(k, curr_val, str(v))

            if cover_bytes:
                table.add_row(
                    "cover_art",
                    "Embedded" if info.get("cover_art_data") else "None",
                    f"Embedded ({len(cover_bytes)} bytes)",
                )

            console.print(table)

            if not dry_run:
                AudioTagger.update_tags(file_path, updates, cover_data=cover_bytes)

        if reorganize:
            console.print("\n[bold magenta]Reorganizing updated tracks...[/bold magenta]")
            moved = pipeline.reorganize_paths(target_files, dry_run=dry_run)
            if moved:
                title_text = (
                    f"[bold yellow]Reorganized Tracks (DRY-RUN: {len(moved)} would move)[/bold yellow]"
                    if dry_run
                    else f"Reorganized Tracks ({len(moved)} moved)"
                )
                header_style = "bold yellow" if dry_run else "bold cyan"
                rtable = Table(title=title_text, show_header=True, header_style=header_style)
                rtable.add_column("Original Location", style="dim")
                rtable.add_column("New Organized Location", style="yellow" if dry_run else "green")
                for old_p, new_p in moved:
                    rtable.add_row(str(old_p), str(new_p))
                console.print(rtable)

    @app.command(name="edit")
    def edit_cmd(
        paths: list[Path] = typer.Argument(
            ...,
            help="Path to audio file(s) or directories to batch edit",
        ),
        replace_title: tuple[str, str] | None = typer.Option(
            None,
            "--replace-title",
            help="Replace substring in title: --replace-title OLD NEW",
        ),
        replace_artist: tuple[str, str] | None = typer.Option(
            None,
            "--replace-artist",
            help="Replace substring in artist: --replace-artist OLD NEW",
        ),
        replace_album: tuple[str, str] | None = typer.Option(
            None,
            "--replace-album",
            help="Replace substring in album: --replace-album OLD NEW",
        ),
        replace_genre: tuple[str, str] | None = typer.Option(
            None,
            "--replace-genre",
            help="Replace substring in genre: --replace-genre OLD NEW",
        ),
        regex_title: tuple[str, str] | None = typer.Option(
            None,
            "--regex-title",
            help="Regex replace in title: --regex-title PATTERN REPLACEMENT",
        ),
        regex_artist: tuple[str, str] | None = typer.Option(
            None,
            "--regex-artist",
            help="Regex replace in artist: --regex-artist PATTERN REPLACEMENT",
        ),
        regex_album: tuple[str, str] | None = typer.Option(
            None,
            "--regex-album",
            help="Regex replace in album: --regex-album PATTERN REPLACEMENT",
        ),
        reorganize: bool = typer.Option(
            False,
            "--reorganize",
            "-r",
            help="Automatically relocate files if artist or album changes",
        ),
        dry_run: bool = typer.Option(
            False, "--dry-run", "-n", help="Preview regex replacements without writing to disk"
        ),
    ):
        """[bold green]Batch Edit Metadata[/bold green]: Find and replace text or regex patterns in metadata tags across tracks."""
        target_files: list[Path] = []
        for p in paths:
            if not p.exists():
                console.print(f"[bold red]Path does not exist:[/bold red] {p}")
                continue
            if p.is_file():
                if p.suffix.lower() in AUDIO_EXTENSIONS:
                    target_files.append(p)
            elif p.is_dir():
                target_files.extend(
                    [
                        f
                        for f in p.rglob("*")
                        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS
                    ]
                )

        target_files = sorted(list(set(target_files)))
        if not target_files:
            console.print("[yellow]No audio files found to edit.[/yellow]")
            return

        config = load_config()
        pipeline = ProcessingPipeline(config)
        modified_count = 0

        for file_path in target_files:
            info = pipeline.extract_file_info(file_path)
            updates = {}

            # 1. Title replacements
            curr_title = info.get("title") or ""
            new_title = curr_title
            if replace_title:
                old_sub, new_sub = replace_title
                new_title = new_title.replace(old_sub, new_sub)
            if regex_title:
                pat, repl = regex_title
                new_title = re.sub(pat, repl, new_title)
            if new_title != curr_title:
                updates["title"] = new_title

            # 2. Artist replacements
            curr_artist = info.get("artist") or ""
            new_artist = curr_artist
            if replace_artist:
                old_sub, new_sub = replace_artist
                new_artist = new_artist.replace(old_sub, new_sub)
            if regex_artist:
                pat, repl = regex_artist
                new_artist = re.sub(pat, repl, new_artist)
            if new_artist != curr_artist:
                updates["artist"] = new_artist

            # 3. Album replacements
            curr_album = info.get("album") or ""
            new_album = curr_album
            if replace_album:
                old_sub, new_sub = replace_album
                new_album = new_album.replace(old_sub, new_sub)
            if regex_album:
                pat, repl = regex_album
                new_album = re.sub(pat, repl, new_album)
            if new_album != curr_album:
                updates["album"] = new_album

            # 4. Genre replacements
            curr_genre = info.get("genre") or ""
            new_genre = curr_genre
            if replace_genre:
                old_sub, new_sub = replace_genre
                new_genre = new_genre.replace(old_sub, new_genre)
            if new_genre != curr_genre:
                updates["genre"] = new_genre

            if updates:
                modified_count += 1
                table_title = (
                    f"[bold yellow]Edit Tags (DRY-RUN): {file_path.name}[/bold yellow]"
                    if dry_run
                    else f"Edit Tags: {file_path.name}"
                )
                table = Table(
                    title=table_title,
                    show_header=True,
                    header_style="bold yellow" if dry_run else "bold cyan",
                )
                table.add_column("Tag", style="bold yellow")
                table.add_column("Original Value", style="dim")
                table.add_column("New Value", style="yellow" if dry_run else "green")

                for k, v in updates.items():
                    table.add_row(k, str(info.get(k, "-") or "-"), str(v))

                console.print(table)

                if not dry_run:
                    AudioTagger.update_tags(file_path, updates)

        if modified_count == 0:
            console.print("[green]No files matched the replacement patterns.[/green]")
            return

        if reorganize:
            console.print("\n[bold magenta]Reorganizing updated tracks...[/bold magenta]")
            moved = pipeline.reorganize_paths(target_files, dry_run=dry_run)
            if moved:
                title_text = (
                    f"[bold yellow]Reorganized Tracks (DRY-RUN: {len(moved)} would move)[/bold yellow]"
                    if dry_run
                    else f"Reorganized Tracks ({len(moved)} moved)"
                )
                header_style = "bold yellow" if dry_run else "bold cyan"
                rtable = Table(title=title_text, show_header=True, header_style=header_style)
                rtable.add_column("Original Location", style="dim")
                rtable.add_column("New Organized Location", style="yellow" if dry_run else "green")
                for old_p, new_p in moved:
                    rtable.add_row(str(old_p), str(new_p))
                console.print(rtable)
