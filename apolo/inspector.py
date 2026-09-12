import base64
import io
import os
from pathlib import Path
from typing import Any, Dict, Optional
import mutagen
from mutagen.flac import Picture
from PIL import Image
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from apolo.utils import format_duration


def get_first_tag(tags: Any, keys: list[str]) -> Optional[str]:
    if not tags:
        return None
    for k in keys:
        try:
            if k in tags:
                val = tags[k]
                if isinstance(val, (list, tuple)) and val:
                    return str(val[0])
                return str(val)
        except Exception:
            pass
        try:
            k_upper = k.upper()
            if k_upper in tags:
                val = tags[k_upper]
                if isinstance(val, (list, tuple)) and val:
                    return str(val[0])
                return str(val)
        except Exception:
            pass
        try:
            k_lower = k.lower()
            if k_lower in tags:
                val = tags[k_lower]
                if isinstance(val, (list, tuple)) and val:
                    return str(val[0])
                return str(val)
        except Exception:
            pass
    return None


def inspect_track(file_path: Path, console: Optional[Console] = None) -> None:
    if console is None:
        console = Console()

    if not file_path.exists():
        console.print(f"[bold red]File not found:[/bold red] {file_path}")
        return

    try:
        audio = mutagen.File(file_path)
    except Exception as e:
        console.print(f"[bold red]Error opening file:[/bold red] {e}")
        return

    tags = getattr(audio, "tags", {}) or {}
    info = getattr(audio, "info", None)

    # Audio stream properties
    duration_str = format_duration(getattr(info, "length", None))
    channels = getattr(info, "channels", "-")
    sample_rate = f"{getattr(info, 'sample_rate', '-')} Hz"
    bitrate = f"{int(getattr(info, 'bitrate', 0) / 1000)} kbps" if getattr(info, "bitrate", 0) else "-"
    file_size = f"{file_path.stat().st_size / (1024 * 1024):.2f} MB"

    # Metadata fields
    title = get_first_tag(tags, ["TITLE", "title", "TIT2"]) or "-"
    artist = get_first_tag(tags, ["ARTIST", "artist", "TPE1"]) or "-"
    album_artist = get_first_tag(tags, ["ALBUMARTIST", "albumartist", "TPE2"]) or "-"
    album = get_first_tag(tags, ["ALBUM", "album", "TALB"]) or "-"
    track_num = get_first_tag(tags, ["TRACKNUMBER", "tracknumber", "TRCK"]) or "-"
    track_total = get_first_tag(tags, ["TRACKTOTAL", "tracktotal", "totaltracks"]) or "-"
    disc_num = get_first_tag(tags, ["DISCNUMBER", "discnumber", "TPOS"]) or "-"
    disc_total = get_first_tag(tags, ["DISCTOTAL", "disctotal", "totaldiscs"]) or "-"
    date = get_first_tag(tags, ["DATE", "date", "TDRC", "TYER"]) or "-"
    genre = get_first_tag(tags, ["GENRE", "genre", "TCON"]) or "-"
    compilation = get_first_tag(tags, ["COMPILATION", "compilation", "TCMP"]) or "-"

    # Lyrics check
    lyrics_raw = get_first_tag(tags, ["LYRICS", "lyrics", "USLT"])
    has_embedded_lyrics = bool(lyrics_raw)
    is_synced = "[" in (lyrics_raw or "") and "]" in (lyrics_raw or "")
    sidecar_lrc = file_path.with_suffix(".lrc")
    has_sidecar_lrc = sidecar_lrc.exists()

    lyrics_status = []
    if is_synced:
        lyrics_status.append("Embedded Synced [LRC]")
    elif has_embedded_lyrics:
        lyrics_status.append("Embedded Plain Text")
    if has_sidecar_lrc:
        lyrics_status.append(f"Sidecar ({sidecar_lrc.name})")
    lyrics_display = ", ".join(lyrics_status) if lyrics_status else "None"

    # Cover Art check
    cover_info = "None"
    # Check Vorbis METADATA_BLOCK_PICTURE
    try:
        if tags and "METADATA_BLOCK_PICTURE" in tags:
            try:
                raw_b64 = tags["METADATA_BLOCK_PICTURE"][0]
                pic_bytes = base64.b64decode(raw_b64)
                pic = Picture(pic_bytes)
                cover_info = f"Embedded ({pic.mime}, {pic.width}x{pic.height}, {len(pic.data)//1024} KB)"
            except Exception:
                cover_info = "Embedded (Vorbis Picture Block)"
        elif hasattr(audio, "pictures") and audio.pictures:
            pic = audio.pictures[0]
            cover_info = f"Embedded ({pic.mime}, {pic.width}x{pic.height}, {len(pic.data)//1024} KB)"
        elif hasattr(tags, "getall") and tags.getall("APIC"):
            apic = tags.getall("APIC")[0]
            cover_info = f"Embedded ID3 APIC ({apic.mime}, {len(apic.data)//1024} KB)"
        elif hasattr(tags, "__contains__") and "covr" in tags and tags["covr"]:
            cover_info = "Embedded MP4 Cover"
    except Exception:
        pass

    # Main Metadata Table
    table = Table(title=f"Metadata Inspector: {file_path.name}", show_header=True, header_style="bold cyan")
    table.add_column("Property", style="bold yellow", width=18)
    table.add_column("Value", style="white")

    table.add_row("File Path", str(file_path))
    table.add_row("Format / Codec", f"{file_path.suffix.upper().lstrip('.')} ({audio.mime[0] if getattr(audio, 'mime', None) else 'Audio'})")
    table.add_row("Audio Specs", f"Duration: {duration_str} | Bitrate: {bitrate} | Sample Rate: {sample_rate} | Channels: {channels} | Size: {file_size}")
    table.add_section()
    table.add_row("Title", title)
    table.add_row("Artist", artist)
    table.add_row("Album Artist", album_artist)
    table.add_row("Album", album)
    table.add_row("Track / Total", f"{track_num} / {track_total}")
    table.add_row("Disc / Total", f"{disc_num} / {disc_total}")
    table.add_row("Release Date", date)
    table.add_row("Genre", genre)
    table.add_row("Compilation", compilation)
    table.add_section()
    table.add_row("Cover Art", cover_info)
    table.add_row("Lyrics", lyrics_display)

    console.print()
    console.print(table)

    # Show preview of lyrics if present
    preview_lyrics = lyrics_raw or (sidecar_lrc.read_text(encoding="utf-8", errors="ignore") if has_sidecar_lrc else None)
    if preview_lyrics:
        lines = [l.strip() for l in preview_lyrics.splitlines() if l.strip()][:8]
        preview_text = "\n".join(lines)
        if len(preview_lyrics.splitlines()) > 8:
            preview_text += "\n..."
        console.print(Panel(preview_text, title="Lyrics Preview", border_style="dim cyan"))
    console.print()
