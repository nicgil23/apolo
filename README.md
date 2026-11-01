<div align="center">

# Apolo

**The audiophile-grade music downloader, tagger, and library organizer for your terminal.**

[![Python 3.14](https://img.shields.io/badge/python-3.14-blue.svg?style=flat-square)](https://www.python.org/)
[![CI Workflow](https://img.shields.io/github/actions/workflow/status/hypr/apolo/ci.yml?branch=main&label=CI&style=flat-square)](.github/workflows/ci.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json&style=flat-square)](https://github.com/astral-sh/ruff)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPLv3-green.svg?style=flat-square)](LICENSE)

[Quickstart](#60-second-quickstart) •
[CLI Cheatsheet](#cli-cheatsheet) •
[Features](#key-features) •
[Yazi](#yazi-file-manager-integration) •
[Browser Extension](#browser-extension) •
[Wiki & Guides](#documentation-wiki)

</div>

---

## 60-Second Quickstart

### 1. Prerequisites
Ensure `ffmpeg` is installed on your system:
```bash
# Arch Linux
sudo pacman -S ffmpeg chromaprint

# Ubuntu / Debian
sudo apt install ffmpeg libchromaprint-tools

# Fedora
sudo dnf install ffmpeg chromaprint-tools
```

### 2. Install Apolo
Using [uv](https://github.com/astral-sh/uv) (recommended) or [pipx](https://pypa.github.io/pipx/):
```bash
uv tool install .
# or
pipx install .
```

### 3. Start Managing Music
```bash
# Download and auto-tag a song from YouTube or SoundCloud
apolo download "https://www.youtube.com/watch?v=5NV6Rdv1a3I"

# Or drop downloaded songs into ~/Music/Inbox and ingest them all at once:
apolo inbox

# Audit your collection health and fix missing lyrics / covers automatically:
apolo doctor --repair-all
```

---

## CLI Cheatsheet

| Command | Alias | What It Does | Example |
| :--- | :--- | :--- | :--- |
| `download` | `adl` | Download from YouTube/SoundCloud, transcode, tag & sort | `apolo download "https://..." -i` |
| `process` | `tag` | Ingest local audio file(s) or folders with full tagging | `apolo process ~/Downloads/album/` |
| `inbox` | - | Ingest and organize all files waiting in `~/Music/Inbox` | `apolo inbox --keep-lossless` |
| `doctor` | - | Audit health score, duplicates, and batch repair collection | `apolo doctor --repair-all` |
| `playlist` | - | Dynamic M3U8 smart playlists, path healing & DAP export | `apolo playlist create "80s" --year "1980..1989"` |
| `set` | - | Fast in-place metadata tagger and cover art embedder | `apolo set song.opus --year 2001 -r` |
| `edit` | - | Bulk regex search-and-replace for messy titles or artists | `apolo edit . --regex-title "\s*\[.*\]" ""` |
| `info` | `inspect` | Pretty-print Vorbis/FLAC metadata, bitrate & cover specs | `apolo info "track.opus"` |
| `gain` | - | ITU-R BS.1770 / EBU R128 loudness normalization tags | `apolo gain ~/Music/Apolo/` |
| `identify` | - | Waveform acoustic fingerprinting via AcoustID | `apolo identify "unknown.mp3" --apply` |
| `cover` | - | Extract embedded art to `cover.jpg` or embed new art | `apolo cover extract ~/Music/Apolo/` |
| `watch` | `daemon`| Background inbox watcher with desktop notifications | `apolo watch` |
| `serve` | - | Local REST API daemon for browser extensions | `apolo serve` |

*Add `--dry-run` (`-n`) to simulate any modification without writing to disk.*

---

## Key Features

### Audiophile Transcoding & Hybrid Lossless
* **Opus 256k VBR**: Default conversion to state-of-the-art Opus (`libopus`, 48 kHz, compression level 10) for transparent quality and compact storage.
* **Bit-Perfect FLAC (`preserve_lossless`)**: Preserves native lossless FLAC streams intact without lossy transcoding while embedding full metadata, synced lyrics, and artwork. Set permanently in `config.toml` or override per-command with `--keep-lossless` / `--to-opus`.

### Multi-Provider Metadata & Synced Lyrics
* Queries **Deezer**, **Apple iTunes**, and **MusicBrainz** concurrently without requiring API keys.
* Ranked candidate matching with interactive selection (`--interactive` / `-i`).
* Synchronized, millisecond-timestamped lyrics fetched from **LRCLIB**, embedded directly and saved as sidecar `.lrc` files.

### Library Doctor & Controlled Anomalies
* Automated **Health Score (0-100%)** diagnosing duplicate files, missing tracks, fragmented albums, and unnormalized genres.
* **Controlled Anomalies (`--control`)**: Exclude intentional partial albums (e.g., favorite tracks from a large discography) from penalty scores.
* One-click automated batch repairs for missing lyrics (`--repair-lyrics`), missing high-res covers (`--repair-covers`), and fragmented artists (`--repair-fragmented`).

### EBU R128 Loudness Normalization
* Non-destructive volume leveling based on the modern **EBU R128 / ITU-R BS.1770** standard.
* Calculates Integrated Loudness (LUFS) and True Peak, writing standard `R128_TRACK_GAIN` and `REPLAYGAIN_*` tags.

### Smart Playlists & DAP / USB Export
* Generate dynamic M3U8 playlists based on metadata filters (`--genre`, `--year`, `--artist`).
* Automatic path healing (`apolo playlist repair`) restores broken playlists after library reorganizations.
* Direct export (`apolo playlist export`) rewrites relative paths and copies tracks for DAPs (Sony Walkman, FiiO) and car USB drives.

---

## Yazi File Manager Integration

Apolo integrates directly with the blazing-fast [Yazi](https://github.com/sxyazi/yazi) terminal file manager:

* **Openers**: Press <kbd>Enter</kbd> or <kbd>o</kbd> on any media file to tag and organize or inspect metadata.
* **Command Palette (<kbd>A</kbd>)**: Full keyboard suite for tagging (<kbd>A</kbd><kbd>t</kbd>), interactive review (<kbd>A</kbd><kbd>T</kbd>), downloading (<kbd>A</kbd><kbd>d</kbd>), running Doctor (<kbd>A</kbd><kbd>D</kbd>), loudness gain (<kbd>A</kbd><kbd>g</kbd>), and AcoustID fingerprinting (<kbd>A</kbd><kbd>f</kbd>).
* **Navigation**: Jump directly to your library with <kbd>g</kbd><kbd>a</kbd>.

*See the full setup in the [Yazi Integration Guide](docs/05-yazi-integration.md).*

---

## Browser Extension

Apolo includes a **Manifest V3** browser extension for Chromium browsers (Brave, Helium, Chrome, Edge) and Firefox under [`plugins/youtube/`](plugins/youtube).

* Adds native download buttons directly to video pages and playlist headers on **YouTube**.
* Adds single-track and album download buttons on **YouTube Music**.
* Dispatches downloads asynchronously to `apolo serve` (`http://127.0.0.1:4533`).

*See setup instructions in the [Browser Extension Guide](docs/06-browser-extension.md).*

---

## Configuration (`~/.config/apolo/config.toml`)

```toml
[directories]
library_dir = "~/Music/Apolo"
inbox_dir   = "~/Music/Inbox"
temp_dir    = "~/.cache/apolo/temp"

[organization]
path_template          = "{artist}/{album} ({date})/{track:02d} - {title}.opus"
save_lrc_file          = true
embed_cover_art        = true
max_cover_size         = 1400
multi_disc_folder      = true
various_artists_folder = true
group_singles          = true
collision_strategy     = "skip"  # "skip", "rename", "overwrite"

[downloader]
audio_format         = "opus"
audio_quality        = "0"
concurrent_downloads = 3
preserve_lossless    = false  # Set to true to permanently keep FLAC files without converting to Opus

[providers]
prefer_deezer      = true
prefer_itunes      = true
prefer_musicbrainz = true
synced_lyrics_only = true

[doctor]
controlled_anomalies = []
```

---

## Documentation (Wiki)

Explore in-depth guides for advanced features and setup:

1. [**Installation & Setup**](docs/01-installation-and-setup.md): Package installation, OS dependencies, config options, and library path template syntax.
2. [**CLI Reference & Workflows**](docs/02-cli-reference-and-workflows.md): Complete flag documentation, interactive workflows, and dry-run simulations.
3. [**Library Doctor & Maintenance**](docs/03-library-doctor.md): Health scoring, intentional controlled anomalies, and automated batch repairs.
4. [**Audio & Tagging Specifications**](docs/04-audio-and-tagging.md): Opus transcoder specs, `--keep-lossless` mode, EBU R128 loudness, and AcoustID.
5. [**Yazi File Manager Integration**](docs/05-yazi-integration.md): Opener rules and the complete `<kbd>A</kbd>` keyboard shortcut palette.
6. [**Browser Extension & Local Daemon**](docs/06-browser-extension.md): Chrome/Firefox extension setup and `systemd` user service configuration.
7. [**Smart Playlists & DAP Export**](docs/07-smart-playlists.md): M3U8 dynamic filters, path healing, and portable USB/DAP exporting.
8. [**Architecture & Development**](docs/08-architecture-and-development.md): Modular package design, testing with `pytest`, and linting with `ruff`.

---

## License

Distributed under the **GNU General Public License v3.0**. See [`LICENSE`](LICENSE) for details.
