import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class DirectoriesConfig:
    library_dir: Path = field(default_factory=lambda: Path.home() / "Music" / "Apolo")
    inbox_dir: Path = field(default_factory=lambda: Path.home() / "Music" / "Inbox")
    temp_dir: Path = field(default_factory=lambda: Path.home() / ".cache" / "apolo" / "temp")


@dataclass
class OrganizationConfig:
    path_template: str = "{artist}/{album} ({date})/{track:02d} - {title}.opus"
    save_lrc_file: bool = True
    embed_cover_art: bool = True
    max_cover_size: int = 1400
    multi_disc_folder: bool = True
    various_artists_folder: bool = True
    group_singles: bool = True
    collision_strategy: str = "skip"  # Options: "skip", "rename", "overwrite"


@dataclass
class DownloaderConfig:
    audio_format: str = "opus"
    audio_quality: str = "0"
    concurrent_downloads: int = 3


@dataclass
class ProvidersConfig:
    prefer_deezer: bool = True
    prefer_itunes: bool = True
    prefer_musicbrainz: bool = True
    synced_lyrics_only: bool = True


@dataclass
class ApoloConfig:
    directories: DirectoriesConfig = field(default_factory=DirectoriesConfig)
    organization: OrganizationConfig = field(default_factory=OrganizationConfig)
    downloader: DownloaderConfig = field(default_factory=DownloaderConfig)
    providers: ProvidersConfig = field(default_factory=ProvidersConfig)


def get_config_path() -> Path:
    config_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "apolo"
    return config_dir / "config.toml"


def load_config(config_path: Optional[Path] = None) -> ApoloConfig:
    target_path = config_path or get_config_path()
    if not target_path.exists():
        return ApoloConfig()

    try:
        with open(target_path, "rb") as f:
            data = tomllib.load(f)
    except Exception:
        return ApoloConfig()

    dirs_data = data.get("directories", {})
    org_data = data.get("organization", {})
    dl_data = data.get("downloader", {})
    prov_data = data.get("providers", {})

    directories = DirectoriesConfig(
        library_dir=Path(os.path.expanduser(dirs_data.get("library_dir", "~/Music/Apolo"))),
        inbox_dir=Path(os.path.expanduser(dirs_data.get("inbox_dir", "~/Music/Inbox"))),
        temp_dir=Path(os.path.expanduser(dirs_data.get("temp_dir", "~/.cache/apolo/temp"))),
    )

    organization = OrganizationConfig(
        path_template=org_data.get("path_template", "{artist}/{album} ({date})/{track:02d} - {title}.opus"),
        save_lrc_file=org_data.get("save_lrc_file", True),
        embed_cover_art=org_data.get("embed_cover_art", True),
        max_cover_size=org_data.get("max_cover_size", 1400),
        multi_disc_folder=org_data.get("multi_disc_folder", True),
        various_artists_folder=org_data.get("various_artists_folder", True),
        group_singles=org_data.get("group_singles", True),
        collision_strategy=org_data.get("collision_strategy", "skip"),
    )

    downloader = DownloaderConfig(
        audio_format=dl_data.get("audio_format", "opus"),
        audio_quality=str(dl_data.get("audio_quality", "0")),
        concurrent_downloads=int(dl_data.get("concurrent_downloads", 3)),
    )

    providers = ProvidersConfig(
        prefer_deezer=prov_data.get("prefer_deezer", True),
        prefer_itunes=prov_data.get("prefer_itunes", True),
        prefer_musicbrainz=prov_data.get("prefer_musicbrainz", True),
        synced_lyrics_only=prov_data.get("synced_lyrics_only", True),
    )

    return ApoloConfig(
        directories=directories,
        organization=organization,
        downloader=downloader,
        providers=providers,
    )
