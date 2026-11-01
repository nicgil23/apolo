import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


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
    audio_bitrate: str = "256k"
    default_origin: str = "local"
    preserve_existing_tags: bool = True
    preserve_lossless: bool = False
    concurrent_downloads: int = 3


@dataclass
class ProvidersConfig:
    prefer_deezer: bool = True
    prefer_itunes: bool = True
    prefer_musicbrainz: bool = True
    synced_lyrics_only: bool = True


@dataclass
class DoctorConfig:
    controlled_anomalies: list[str] = field(default_factory=list)
    show_controlled_anomalies: bool = True
    show_missing_lyrics: bool = True


@dataclass
class ApoloConfig:
    directories: DirectoriesConfig = field(default_factory=DirectoriesConfig)
    organization: OrganizationConfig = field(default_factory=OrganizationConfig)
    downloader: DownloaderConfig = field(default_factory=DownloaderConfig)
    providers: ProvidersConfig = field(default_factory=ProvidersConfig)
    doctor: DoctorConfig = field(default_factory=DoctorConfig)


def get_config_path() -> Path:
    config_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "apolo"
    return config_dir / "config.toml"


def load_config(config_path: Path | None = None) -> ApoloConfig:
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
    doc_data = data.get("doctor", {})

    directories = DirectoriesConfig(
        library_dir=Path(os.path.expanduser(dirs_data.get("library_dir", "~/Music/Apolo"))),
        inbox_dir=Path(os.path.expanduser(dirs_data.get("inbox_dir", "~/Music/Inbox"))),
        temp_dir=Path(os.path.expanduser(dirs_data.get("temp_dir", "~/.cache/apolo/temp"))),
    )

    organization = OrganizationConfig(
        path_template=org_data.get(
            "path_template", "{artist}/{album} ({date})/{track:02d} - {title}.opus"
        ),
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
        audio_bitrate=str(dl_data.get("audio_bitrate", "256k")),
        default_origin=str(dl_data.get("default_origin", "local")),
        preserve_existing_tags=bool(dl_data.get("preserve_existing_tags", True)),
        preserve_lossless=bool(dl_data.get("preserve_lossless", False)),
        concurrent_downloads=int(dl_data.get("concurrent_downloads", 3)),
    )

    providers = ProvidersConfig(
        prefer_deezer=prov_data.get("prefer_deezer", True),
        prefer_itunes=prov_data.get("prefer_itunes", True),
        prefer_musicbrainz=prov_data.get("prefer_musicbrainz", True),
        synced_lyrics_only=prov_data.get("synced_lyrics_only", True),
    )

    controlled = [
        str(x).strip() for x in doc_data.get("controlled_anomalies", []) if str(x).strip()
    ]
    show_controlled = doc_data.get(
        "show_controlled_anomalies",
        doc_data.get("show_controlled", doc_data.get("show_anomalies", True)),
    )
    show_lyrics = doc_data.get("show_missing_lyrics", doc_data.get("show_lyrics", True))
    doctor = DoctorConfig(
        controlled_anomalies=controlled,
        show_controlled_anomalies=bool(show_controlled),
        show_missing_lyrics=bool(show_lyrics),
    )

    return ApoloConfig(
        directories=directories,
        organization=organization,
        downloader=downloader,
        providers=providers,
        doctor=doctor,
    )


def save_doctor_controlled_anomalies(anomalies: list[str], config_path: Path | None = None) -> Path:
    target_path = config_path or get_config_path()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    content = ""
    if target_path.exists():
        content = target_path.read_text(encoding="utf-8")

    # Format list
    unique_items = []
    for it in anomalies:
        c = it.strip()
        if c and c not in unique_items:
            unique_items.append(c)

    formatted_items = ",\n".join(f'    "{item}"' for item in unique_items)
    anomalies_block = (
        f"controlled_anomalies = [\n{formatted_items}\n]"
        if unique_items
        else "controlled_anomalies = []"
    )

    import re

    if re.search(r"^\[doctor\]", content, flags=re.MULTILINE):
        # If controlled_anomalies setting already exists under [doctor], replace only that block
        if re.search(r"controlled_anomalies\s*=\s*\[[^\]]*\]", content):
            new_content = re.sub(r"controlled_anomalies\s*=\s*\[[^\]]*\]", anomalies_block, content)
        else:
            # Insert controlled_anomalies right under [doctor] header
            new_content = re.sub(r"(\[doctor\]\s*)", rf"\1{anomalies_block}\n", content, count=1)
        target_path.write_text(new_content, encoding="utf-8")
    else:
        # Append [doctor] section
        doctor_section = f"[doctor]\n{anomalies_block}\n"
        new_content = content.rstrip() + "\n\n" + doctor_section
        target_path.write_text(new_content.strip() + "\n", encoding="utf-8")

    return target_path
