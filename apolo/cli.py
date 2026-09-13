import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from apolo.config import get_config_path, load_config
from apolo.metadata.models import METADATOS_BIBLIOTECA, TrackMetadata
from apolo.pipeline import AUDIO_EXTENSIONS, ProcessingPipeline
from apolo.tagger import AudioTagger


app = typer.Typer(
    name="apolo",
    help="""[bold cyan]Apolo[/bold cyan] - Modern CLI Music Suite: Lossless/Hi-Fi Audio Transcoder, Smart Tagger, Acoustic Fingerprinter & Library Manager.

[bold yellow]Key Features & Capabilities:[/bold yellow]
  • [green]Audio Transcoding & Lossless Preservation[/green]: Converts any audio/video to high-quality [bold].opus[/bold] (256k VBR) or preserves pristine bit-perfect [bold].flac[/bold] ([bold]--keep-lossless[/bold]).
  • [green]Metadata Tagging & Interactive Selection[/green]: Multi-source lookup (Deezer, iTunes, MusicBrainz) with interactive candidate review ([bold]--interactive[/bold] / [bold]-i[/bold]).
  • [green]Acoustic Fingerprinting[/green]: Identify unknown and untagged tracks by waveform using Chromaprint & AcoustID ([bold]apolo identify[/bold]).
  • [green]EBU R128 & ReplayGain[/green]: Loudness normalization tagging ([bold]R128_TRACK_GAIN[/bold] / [bold]REPLAYGAIN_*[/bold]) via FFmpeg ebur128 ([bold]apolo gain[/bold]).
  • [green]Library Health & Diagnostics[/green]: Audit duplicate tracks, missing album tracks, missing lyrics/covers, and run automated repairs ([bold]apolo doctor[/bold]).
  • [green]Smart Playlists & Export[/green]: Dynamic M3U8 playlists by genre/year/artist, auto-relinking broken paths, and export to DAPs/USB ([bold]apolo playlist[/bold]).
  • [green]Watcher Daemon[/green]: Background folder monitoring with debounce and desktop notifications ([bold]apolo watch[/bold]).
  • [green]Cover Art Utilities[/green]: Extract embedded covers to [bold]cover.jpg[/bold] for media servers (Navidrome/Jellyfin) or embed HD art ([bold]apolo cover[/bold]).
  • [green]Tag Editor & Simulation[/green]: In-place editing ([bold]set / edit[/bold]) and safe dry-run previewing ([bold]--dry-run[/bold]).""",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


def display_track_summary(dest_audio: Path, dest_lrc: Optional[Path], meta: TrackMetadata, dry_run: bool = False) -> None:
    title_text = "[bold yellow]Apolo Simulation (DRY-RUN - No files modified)[/bold yellow]" if dry_run else "Apolo Processed Track"
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
    table.add_row("Cover Art", "Embedded (High Quality)" if meta.cover_art_data or meta.cover_art_url else "None")
    table.add_row("Synced Lyrics", "Embedded + Sidecar .lrc" if dest_lrc else ("Embedded" if meta.synced_lyrics else "Not found"))
    table.add_row("Destination" + (" (Simulated)" if dry_run else ""), str(dest_audio))

    console.print(table)
    console.print()


def make_cli_candidate_selector(matcher, console_instance):
    def selector(candidates: List[Tuple[float, TrackMetadata]], query: str) -> Optional[TrackMetadata]:
        curr_candidates = candidates
        curr_query = query
        while True:
            if not curr_candidates:
                console_instance.print(f"[yellow]No candidates available for:[/yellow] {curr_query}")
                return None

            table = Table(title=f"Metadata Candidates for: [bold yellow]{curr_query}[/bold yellow]", show_header=True, header_style="bold cyan")
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
            console_instance.print("[dim]Options: [1-N] Select candidate | [0 / s] Skip / Use default metadata | [m] Manual search query[/dim]")

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
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Interactively review and select candidate metadata from online providers.",
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
        help="Simulate processing and tagging without modifying files or filesystem.",
    ),
):
    """[bold green]Process and Tag[/bold green] existing audio or video files into high-quality [bold].opus[/bold] (or FLAC if lossless), preserve valid metadata, tag origin, and organize into library."""
    config = load_config()
    pipeline = ProcessingPipeline(config)
    selector = make_cli_candidate_selector(pipeline.matcher, console) if interactive else None

    for path in paths:
        if not path.exists():
            console.print(f"[bold red]Path does not exist:[/bold red] {path}")
            continue

        prefix = "[bold yellow][DRY-RUN][/bold yellow] " if dry_run else ""
        if path.is_dir():
            console.print(f"\n{prefix}[bold magenta]Scanning directory (recursive):[/bold magenta] {path}")
            status_msg = "[bold yellow]Simulating directory scan...[/bold yellow]" if dry_run else "[bold cyan]Processing audio files...[/bold cyan]"
            with console.status(status_msg) as status:
                def update_status(step: str, msg: str):
                    status.update(f"[bold cyan]{msg}[/bold cyan]")

                results = pipeline.process_directory(
                    path,
                    origin=origin,
                    force_rematch=force_rematch,
                    dry_run=dry_run,
                    preserve_lossless=keep_lossless,
                    candidate_selector=selector,
                    on_progress=update_status,
                )
                if not results:
                    console.print(f"[yellow]No supported audio/video files found in:[/yellow] {path}")
                for dest_audio, dest_lrc, meta in results:
                    display_track_summary(dest_audio, dest_lrc, meta, dry_run=dry_run)
        else:
            console.print(f"\n{prefix}[bold magenta]Processing file:[/bold magenta] {path.name}")
            status_msg = "[bold yellow]Simulating file processing...[/bold yellow]" if dry_run else "[bold cyan]Processing audio file...[/bold cyan]"
            with console.status(status_msg) as status:
                def update_status(step: str, msg: str):
                    status.update(f"[bold cyan]{msg}[/bold cyan]")

                res = pipeline.process_file(
                    path,
                    origin=origin,
                    force_rematch=force_rematch,
                    dry_run=dry_run,
                    preserve_lossless=keep_lossless,
                    candidate_selector=selector,
                    on_progress=update_status,
                )
                if res:
                    dest_audio, dest_lrc, meta = res
                    display_track_summary(dest_audio, dest_lrc, meta, dry_run=dry_run)
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
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Interactively review and select candidate metadata from online providers.",
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
        help="Simulate inbox processing without converting or moving files.",
    ),
):
    """[bold green]Inbox Processor[/bold green]: Process and organize all audio/video files dropped into your configured Inbox directory."""
    config = load_config()
    inbox_dir = config.directories.inbox_dir
    if not inbox_dir.exists():
        if not dry_run:
            inbox_dir.mkdir(parents=True, exist_ok=True)
            console.print(f"[bold yellow]Inbox directory was empty/created at {inbox_dir}[/bold yellow]")
        else:
            console.print(f"[bold yellow][DRY-RUN] Inbox directory does not exist yet at {inbox_dir}[/bold yellow]")
        return

    pipeline = ProcessingPipeline(config)
    selector = make_cli_candidate_selector(pipeline.matcher, console) if interactive else None
    prefix = "[bold yellow][DRY-RUN][/bold yellow] " if dry_run else ""
    console.print(f"\n{prefix}[bold magenta]Processing Inbox:[/bold magenta] {inbox_dir}")
    status_msg = "[bold yellow]Simulating inbox audio files...[/bold yellow]" if dry_run else "[bold cyan]Processing inbox audio files...[/bold cyan]"
    with console.status(status_msg) as status:
        def update_status(step: str, msg: str):
            status.update(f"[bold cyan]{msg}[/bold cyan]")

        results = pipeline.process_directory(
            inbox_dir,
            origin=origin,
            force_rematch=force_rematch,
            dry_run=dry_run,
            preserve_lossless=keep_lossless,
            candidate_selector=selector,
            on_progress=update_status,
        )
        if not results:
            console.print("[yellow]No audio files found in inbox.[/yellow]")
        for dest_audio, dest_lrc, meta in results:
            display_track_summary(dest_audio, dest_lrc, meta, dry_run=dry_run)


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


@app.command(name="set")
def set_cmd(
    paths: List[Path] = typer.Argument(
        ...,
        help="Path to audio file(s) or directories to update tags",
    ),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Track title"),
    artist: Optional[str] = typer.Option(None, "--artist", "-a", help="Artist name"),
    album_artist: Optional[str] = typer.Option(None, "--album-artist", "-A", help="Album artist name"),
    album: Optional[str] = typer.Option(None, "--album", "-b", help="Album name"),
    track_number: Optional[int] = typer.Option(None, "--track", "-n", help="Track number"),
    track_total: Optional[int] = typer.Option(None, "--track-total", "-N", help="Total track count"),
    disc_number: Optional[int] = typer.Option(None, "--disc", "-d", help="Disc number"),
    disc_total: Optional[int] = typer.Option(None, "--disc-total", "-D", help="Total disc count"),
    date: Optional[str] = typer.Option(None, "--year", "--date", "-y", help="Release year or date (YYYY or YYYY-MM-DD)"),
    genre: Optional[str] = typer.Option(None, "--genre", "-g", help="Music genre"),
    origin: Optional[str] = typer.Option(None, "--origin", "-o", help="Origin / source identifier"),
    compilation: Optional[bool] = typer.Option(None, "--compilation", "-c", help="Mark as compilation (true/false)"),
    lyrics: Optional[str] = typer.Option(None, "--lyrics", "-l", help="Lyrics text or path to .lrc / .txt file"),
    cover: Optional[Path] = typer.Option(None, "--cover", help="Path to cover art image file to embed"),
    reorganize: bool = typer.Option(False, "--reorganize", "-r", help="Automatically relocate files according to updated metadata"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview tag changes without writing to disk"),
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
    if lyrics_content is not None:
        updates["lyrics"] = lyrics_content

    if not updates and not cover_bytes:
        console.print("[yellow]No tags or cover art specified to update. Use --help to view available options.[/yellow]")
        return

    # Find target files
    target_files: List[Path] = []
    for p in paths:
        if not p.exists():
            console.print(f"[bold red]Path does not exist:[/bold red] {p}")
            continue
        if p.is_file():
            if p.suffix.lower() in AUDIO_EXTENSIONS:
                target_files.append(p)
        elif p.is_dir():
            target_files.extend([f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS])

    target_files = sorted(list(set(target_files)))
    if not target_files:
        console.print("[yellow]No audio files found to update.[/yellow]")
        return

    config = load_config()
    pipeline = ProcessingPipeline(config)

    for file_path in target_files:
        info = pipeline.extract_file_info(file_path)
        table_title = f"[bold yellow]Set Tags (DRY-RUN): {file_path.name}[/bold yellow]" if dry_run else f"Set Tags: {file_path.name}"
        table = Table(title=table_title, show_header=True, header_style="bold yellow" if dry_run else "bold cyan")
        table.add_column("Tag", style="bold yellow")
        table.add_column("Current Value", style="dim")
        table.add_column("New Value", style="yellow" if dry_run else "green")

        for k, v in updates.items():
            curr_val = str(info.get(k, "-") or "-")
            table.add_row(k, curr_val, str(v))

        if cover_bytes:
            table.add_row("cover_art", "Embedded" if info.get("cover_art_data") else "None", f"Embedded ({len(cover_bytes)} bytes)")

        console.print(table)

        if not dry_run:
            AudioTagger.update_tags(file_path, updates, cover_data=cover_bytes)

    if reorganize:
        console.print(f"\n[bold magenta]Reorganizing updated tracks...[/bold magenta]")
        moved = pipeline.reorganize_paths(target_files, dry_run=dry_run)
        if moved:
            title_text = f"[bold yellow]Reorganized Tracks (DRY-RUN: {len(moved)} would move)[/bold yellow]" if dry_run else f"Reorganized Tracks ({len(moved)} moved)"
            header_style = "bold yellow" if dry_run else "bold cyan"
            rtable = Table(title=title_text, show_header=True, header_style=header_style)
            rtable.add_column("Original Location", style="dim")
            rtable.add_column("New Organized Location", style="yellow" if dry_run else "green")
            for old_p, new_p in moved:
                rtable.add_row(str(old_p), str(new_p))
            console.print(rtable)


@app.command(name="edit")
def edit_cmd(
    paths: List[Path] = typer.Argument(
        ...,
        help="Path to audio file(s) or directories to batch edit",
    ),
    replace_title: Optional[Tuple[str, str]] = typer.Option(
        None,
        "--replace-title",
        help="Replace substring in title: --replace-title OLD NEW",
    ),
    replace_artist: Optional[Tuple[str, str]] = typer.Option(
        None,
        "--replace-artist",
        help="Replace substring in artist: --replace-artist OLD NEW",
    ),
    replace_album: Optional[Tuple[str, str]] = typer.Option(
        None,
        "--replace-album",
        help="Replace substring in album: --replace-album OLD NEW",
    ),
    replace_genre: Optional[Tuple[str, str]] = typer.Option(
        None,
        "--replace-genre",
        help="Replace substring in genre: --replace-genre OLD NEW",
    ),
    regex_title: Optional[Tuple[str, str]] = typer.Option(
        None,
        "--regex-title",
        help="Regex replace in title: --regex-title PATTERN REPLACEMENT",
    ),
    regex_artist: Optional[Tuple[str, str]] = typer.Option(
        None,
        "--regex-artist",
        help="Regex replace in artist: --regex-artist PATTERN REPLACEMENT",
    ),
    regex_album: Optional[Tuple[str, str]] = typer.Option(
        None,
        "--regex-album",
        help="Regex replace in album: --regex-album PATTERN REPLACEMENT",
    ),
    reorganize: bool = typer.Option(False, "--reorganize", "-r", help="Automatically relocate files if artist or album changes"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview regex replacements without writing to disk"),
):
    """[bold green]Batch Edit Metadata[/bold green]: Find and replace text or regex patterns in metadata tags across tracks."""
    target_files: List[Path] = []
    for p in paths:
        if not p.exists():
            console.print(f"[bold red]Path does not exist:[/bold red] {p}")
            continue
        if p.is_file():
            if p.suffix.lower() in AUDIO_EXTENSIONS:
                target_files.append(p)
        elif p.is_dir():
            target_files.extend([f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS])

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
            table_title = f"[bold yellow]Edit Tags (DRY-RUN): {file_path.name}[/bold yellow]" if dry_run else f"Edit Tags: {file_path.name}"
            table = Table(title=table_title, show_header=True, header_style="bold yellow" if dry_run else "bold cyan")
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
        console.print(f"\n[bold magenta]Reorganizing updated tracks...[/bold magenta]")
        moved = pipeline.reorganize_paths(target_files, dry_run=dry_run)
        if moved:
            title_text = f"[bold yellow]Reorganized Tracks (DRY-RUN: {len(moved)} would move)[/bold yellow]" if dry_run else f"Reorganized Tracks ({len(moved)} moved)"
            header_style = "bold yellow" if dry_run else "bold cyan"
            rtable = Table(title=title_text, show_header=True, header_style=header_style)
            rtable.add_column("Original Location", style="dim")
            rtable.add_column("New Organized Location", style="yellow" if dry_run else "green")
            for old_p, new_p in moved:
                rtable.add_row(str(old_p), str(new_p))
            console.print(rtable)


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
            files = [p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS]
            if not files:
                console.print(f"[yellow]No supported audio files in {path}[/yellow]")
            for f in sorted(files):
                inspect_track(f, console=console)
        else:
            console.print(f"[bold red]File not found:[/bold red] {path}")


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
    missing_lyrics_only: bool = typer.Option(False, "--missing-lyrics", help="Display tracks missing synced lyrics only"),
    missing_covers_only: bool = typer.Option(False, "--missing-covers", help="Display tracks missing high-res covers only"),
    repair_lyrics: bool = typer.Option(False, "--repair-lyrics", help="Automatically fetch and embed missing synced lyrics from LRCLIB"),
    repair_covers: bool = typer.Option(False, "--repair-covers", help="Automatically fetch and embed missing high-res covers"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Preview repairs without modifying files on disk"),
):
    """[bold green]Library Health & Diagnostics[/bold green]: Audit duplicates, incomplete albums, missing lyrics, and low-res covers with automated batch repairs."""
    from apolo.doctor import LibraryDoctor

    config = load_config()
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
    if repair_lyrics:
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

    if repair_covers:
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

    if repair_lyrics or repair_covers:
        return

    # Filter views if specific flags requested
    show_all = not any([duplicates_only, missing_tracks_only, missing_lyrics_only, missing_covers_only])

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
  • Duplicate Groups:      {len(report.duplicates)}
  • Incomplete Albums:     {len(report.incomplete_albums)}
  • Missing Synced Lyrics: {len(report.missing_lyrics)}
  • Missing/Low-Res Covers:{len(report.missing_or_lowres_covers)}
  • Missing Essential Tags:{len(report.missing_essential_tags)}"""
        console.print(Panel(summary_panel, title="Apolo Library Health Report", border_style=score_color))

    # 2. Duplicates Table
    if (show_all or duplicates_only) and report.duplicates:
        dup_table = Table(title=f"Duplicate Tracks ({len(report.duplicates)} groups)", show_header=True, header_style="bold yellow")
        dup_table.add_column("Artist - Title", style="bold yellow")
        dup_table.add_column("Type", style="dim")
        dup_table.add_column("Locations", style="green")
        for dup in report.duplicates:
            paths_str = "\n".join(str(p) for p in dup.tracks)
            dup_table.add_row(f"{dup.artist} - {dup.title}", dup.match_type, paths_str)
        console.print(dup_table)

    # 3. Incomplete Albums Table
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

    # 4. Missing Lyrics
    if (show_all or missing_lyrics_only) and report.missing_lyrics:
        lyr_table = Table(title=f"Tracks Missing Synced Lyrics ({len(report.missing_lyrics)} tracks)", show_header=True, header_style="bold cyan")
        lyr_table.add_column("File Path", style="cyan")
        for p in report.missing_lyrics[:15]:
            lyr_table.add_row(str(p))
        if len(report.missing_lyrics) > 15:
            lyr_table.add_row(f"[dim]... and {len(report.missing_lyrics) - 15} more (use --repair-lyrics to fetch)[/dim]")
        console.print(lyr_table)

    # 5. Missing / Low-Res Covers
    if (show_all or missing_covers_only) and report.missing_or_lowres_covers:
        cov_table = Table(title=f"Cover Art Issues ({len(report.missing_or_lowres_covers)} tracks)", show_header=True, header_style="bold magenta")
        cov_table.add_column("File Path", style="magenta")
        cov_table.add_column("Issue", style="yellow")
        for p, reason in report.missing_or_lowres_covers[:15]:
            cov_table.add_row(str(p), reason)
        if len(report.missing_or_lowres_covers) > 15:
            cov_table.add_row(f"[dim]... and {len(report.missing_or_lowres_covers) - 15} more (use --repair-covers to fix)[/dim]", "")
        console.print(cov_table)


# Playlist Sub-App
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
    from apolo.playlists import PlaylistManager

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
    from apolo.playlists import PlaylistManager

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
    from apolo.playlists import PlaylistManager

    config = load_config()
    pm = PlaylistManager(config)
    console.print(f"\n[bold magenta]Scanning playlists for broken file paths...[/bold magenta]")

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
    from apolo.playlists import PlaylistManager

    config = load_config()
    pm = PlaylistManager(config)
    try:
        exported_pl, count = pm.export_playlist(name, dest, copy_files=copy_audio)
        console.print(f"[bold green]Exported playlist successfully:[/bold green] {exported_pl.name} [cyan]({count} tracks)[/cyan]")
        console.print(f"[dim]Destination: {dest}[/dim]")
    except Exception as e:
        console.print(f"[bold red]Error exporting playlist:[/bold red] {e}")
        raise typer.Exit(code=1)


# Gain Command (EBU R128 & ReplayGain Normalization)
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
    from apolo.gain import LoudnessScanner

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


# Watcher Daemon Command
@app.command(name="watch")
@app.command(name="daemon", hidden=True)
def watch_cmd(
    watch_dir: Optional[Path] = typer.Option(
        None,
        "--dir",
        "-d",
        help="Directory to monitor (defaults to config inbox_dir)",
    ),
    poll_interval: float = typer.Option(
        2.0,
        "--interval",
        "-i",
        help="Polling interval in seconds",
    ),
    once: bool = typer.Option(
        False,
        "--once",
        help="Run a single scan iteration and exit",
    ),
):
    """[bold green]Inbox Watcher Daemon[/bold green]: Monitor Inbox in the background, auto-transcode and organize new tracks, and send desktop notifications."""
    from apolo.watcher import InboxWatcher

    config = load_config()
    watcher = InboxWatcher(config)
    watcher.run_watch_loop(watch_dir=watch_dir, poll_interval=poll_interval, once=once, console=console)


# Cover Art Sub-App
cover_app = typer.Typer(
    name="cover",
    help="""[bold green]Cover Art Utilities[/bold green]: Extract embedded covers to cover.jpg/folder.jpg for media servers or embed custom covers.""",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
app.add_typer(cover_app, name="cover")


@cover_app.command(name="extract")
def cover_extract_cmd(
    paths: List[Path] = typer.Argument(
        ...,
        help="Audio file(s) or directories to extract cover art from",
    ),
    filename: str = typer.Option(
        "cover.jpg",
        "--name",
        "-n",
        help="Target image filename (e.g. cover.jpg or folder.jpg)",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        "-f",
        help="Overwrite existing cover image files",
    ),
):
    """[bold green]Extract Cover Art[/bold green]: Save embedded cover art as cover.jpg / folder.jpg in each album directory for media servers."""
    from apolo.cover import CoverManager

    extracted = CoverManager.extract_covers(paths, target_filename=filename, overwrite=overwrite)
    if not extracted:
        console.print("[yellow]No embedded covers extracted (already exist or not found).[/yellow]")
        return

    table = Table(title=f"Extracted Cover Art ({len(extracted)} saved)", show_header=True, header_style="bold cyan")
    table.add_column("Source Track", style="dim")
    table.add_column("Extracted Image", style="green")
    for src, out_img in extracted:
        table.add_row(src.name, f"{out_img.parent.name}/{out_img.name}")
    console.print(table)


@cover_app.command(name="set")
def cover_set_cmd(
    paths: List[Path] = typer.Argument(
        ...,
        help="Audio file(s) or directories to update with new cover art",
    ),
    image: Path = typer.Argument(
        ...,
        help="Path to high-resolution image file to embed",
    ),
):
    """[bold green]Set Album Cover[/bold green]: Embed an optimized 1:1 square cover art image into all audio tracks in a directory."""
    try:
        updated = CoverManager.set_album_cover(paths, image)
        console.print(f"[bold green]Successfully embedded cover art into {updated} tracks.[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error embedding cover art:[/bold red] {e}")
        raise typer.Exit(code=1)


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
    from apolo.fingerprint import AcousticFingerprinter

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


@app.command(name="serve")
def serve(
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host address to bind the API server to"),
    port: int = typer.Option(4533, "--port", "-p", help="Port to listen on for REST requests"),
):
    """
    [bold green]Start the Apolo Local REST API Server[/bold green] for browser and desktop plugins (YouTube, Spicetify).

    Listens on [cyan]http://127.0.0.1:4533[/cyan] by default and processes queued downloads in the background.
    """
    from apolo.server import ApoloServer

    config = load_config()
    server = ApoloServer(host=host, port=port, config=config)

    console.print(
        Panel(
            f"[bold green]Apolo REST API Server active[/bold green]\n\n"
            f"• Listening on: [bold cyan]http://{host}:{port}[/bold cyan]\n"
            f"• Endpoints: [yellow]GET /api/status[/yellow], [yellow]POST /api/download[/yellow], [yellow]GET /api/tasks[/yellow]\n"
            f"• Ready to receive requests from YouTube, YouTube Music and Spicetify plugins.\n\n"
            f"[dim]Press Ctrl+C to stop the server[/dim]",
            title="Apolo Daemon Server",
            border_style="green",
        )
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping Apolo REST API Server...[/yellow]")
        server.shutdown()
        console.print("[green]Server stopped successfully.[/green]")


def main():
    app()


if __name__ == "__main__":
    main()
