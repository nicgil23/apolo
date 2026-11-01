import typer

from apolo.cli.commands import (
    config,
    cover,
    doctor,
    download,
    edit,
    gain,
    identify,
    inspect,
    organize,
    playlist,
    process,
    server,
    watcher,
)

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

# Register command groups
download.register(app)
process.register(app)
organize.register(app)
edit.register(app)
config.register(app)
inspect.register(app)
doctor.register(app)
playlist.register(app)
gain.register(app)
watcher.register(app)
cover.register(app)
identify.register(app)
server.register(app)


def main():
    app()


if __name__ == "__main__":
    main()
