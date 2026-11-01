import typer
from rich.panel import Panel

from apolo.cli.ui import console
from apolo.config import get_config_path, load_config


def register(app: typer.Typer) -> None:
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

[bold cyan]Library Doctor:[/bold cyan]
  - Show Detailed Anomalies: {config.doctor.show_controlled_anomalies}
  - Show Missing Lyrics:     {config.doctor.show_missing_lyrics}
  - Controlled Anomaly Rules: {len(config.doctor.controlled_anomalies)}
"""
        console.print(Panel(panel_content, title="Apolo Configuration", border_style="bold blue"))
