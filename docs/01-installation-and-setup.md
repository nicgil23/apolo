# Installation & Setup Guide

Apolo is an automated audio downloader, tagger, and library organizer engineered for audiophiles and terminal-centric workflows. This guide covers system requirements, package installation, and full configuration.

---

## 1. System Requirements & External Binaries

Apolo integrates directly with specialized low-level multimedia tools. Ensure the following binaries are available in your `$PATH`:

| Tool | Status | Purpose |
| :--- | :--- | :--- |
| **`ffmpeg`** | Required | High-fidelity audio extraction, transcoding to Opus, and embedded cover art handling |
| **`ffprobe`** | Required | Stream metadata extraction and audio duration/format inspection |
| **`fpcalc`** (`chromaprint`) | Recommended | Acoustic fingerprinting for waveform matching with AcoustID (`apolo identify`) |
| **`notify-send`** (`libnotify`) | Optional | Desktop push notifications for `apolo watch` daemon |

### Installing External Binaries by Platform

=== "Arch Linux"
```bash
sudo pacman -S ffmpeg chromaprint libnotify
```

=== "Ubuntu / Debian"
```bash
sudo apt update
sudo apt install ffmpeg libchromaprint-tools libnotify-bin
```

=== "Fedora"
```bash
sudo dnf install ffmpeg chromaprint-tools libnotify
```

=== "macOS (Homebrew)"
```bash
brew install ffmpeg chromaprint
```

Verify your environment anytime by running:
```bash
apolo doctor
```
*(Apolo will explicitly alert you if any binary is missing from your system).*

---

## 2. Installing Apolo

Apolo requires **Python >= 3.11** (tested up to **Python 3.14**).

### Recommended: Isolated Tool Installation (`uv tool` / `pipx`)

Installing via isolated tool managers keeps your global environment clean and avoids distro package conflicts:

```bash
# Using uv (fastest)
uv tool install /path/to/apolo

# Or using pipx
pipx install /path/to/apolo
```

### Local Development / Editable Mode

If you are developing or customizing Apolo locally:

```bash
cd /path/to/apolo

# Using uv
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Or using standard pip
pip install -e . --break-system-packages
```

---

## 3. Configuration (`~/.config/apolo/config.toml`)

On first execution, Apolo reads its configuration from `~/.config/apolo/config.toml`. If the file does not exist, defaults are used automatically.

To inspect your active runtime configuration:
```bash
apolo config
```

### Reference Configuration

Save this file to `~/.config/apolo/config.toml`:

```toml
[directories]
# Root directory where your organized music library resides
library_dir = "~/Music/Apolo"

# Staging inbox watched by `apolo inbox` and `apolo watch`
inbox_dir = "~/Music/Inbox"

# Temporary workspace for yt-dlp downloads and raw transcode buffers
temp_dir = "~/.cache/apolo/temp"

[organization]
# Dynamic path format for library placement
path_template = "{artist}/{album} ({date})/{track:02d} - {title}.opus"

# Save sidecar timestamped .lrc files alongside audio tracks
save_lrc_file = true

# Embed high-resolution cover art into Vorbis Comment picture block
embed_cover_art = true

# Maximum bounding box dimension for embedded covers (pixels)
max_cover_size = 1400

# Subdirectories for multi-disc releases (e.g. "Disc 01/")
multi_disc_folder = true

# Route compilation albums to "Various Artists/"
various_artists_folder = true

# Route single releases to "{artist}/Singles/"
group_singles = true

# Collision handling if destination file exists ("skip", "rename", "overwrite")
collision_strategy = "skip"

[downloader]
# Primary target codec ("opus" or "flac")
audio_format = "opus"

# Opus VBR quality setting (0 = highest quality ~160-256 kbps)
audio_quality = "0"

# Maximum parallel downloads for playlists/queues
concurrent_downloads = 3

# Permanently keep FLAC files as bit-perfect FLAC without converting to Opus
preserve_lossless = false

[providers]
# Metadata search priority and provider toggles
prefer_deezer = true
prefer_itunes = true
prefer_musicbrainz = true

# Prefer timestamped synced lyrics ([mm:ss.xx]) over plain text
synced_lyrics_only = true

[doctor]
# List of known incomplete albums/discography folders to ignore in health scoring
controlled_anomalies = []
```

---

## 4. Library Organization & Path Template Syntax

Apolo automatically files your audio into a clean, predictable directory tree. You can fully customize this hierarchy in `~/.config/apolo/config.toml` under `[organization]`.

### Path Template Syntax

The `path_template` option defines the relative destination path inside `library_dir`:

```toml
[organization]
path_template = "{artist}/{album} ({date})/{track:02d} - {title}.opus"
```

All placeholders are wrapped in curly brackets `{placeholder}`. You can use standard Python format specifiers (e.g. `:02d` for zero-padding integers).

#### Available Placeholders

| Variable | Description | Example Value |
| :--- | :--- | :--- |
| `{artist}` | Album artist (if present) or primary track artist (sanitized) | `Daft Punk` |
| `{album_artist}` | Explicit album artist | `Daft Punk` |
| `{track_artist}` | Individual track artist (useful for collaborations and features) | `Daft Punk feat. Pharrell Williams` |
| `{album}` | Album or EP title (sanitized, with disc numbers stripped) | `Discovery` |
| `{title}` | Track title (sanitized) | `Digital Love` |
| `{track}` | Track position integer | `3` |
| `{track:02d}` | Track number zero-padded to two digits | `03` |
| `{track_total}` | Total tracks on album | `14` |
| `{disc}` / `{disc:02d}` | Disc number integer | `1` / `01` |
| `{disc_total}` | Total discs on release | `2` |
| `{year}` | 4-digit release year | `2001` |
| `{date}` | Release date or year string | `2001-03-12` |
| `{decade}` | 4-digit decade group | `2000s`, `1980s` |
| `{genre}` | Primary normalized musical genre | `French House`, `Rock` |
| `{initial}` | Uppercase alphabetical initial (A-Z or # for numbers/symbols) | `D` |
| `{origin}` | Download source identifier | `youtube`, `soundcloud`, `inbox` |
| `{format}` / `{ext}` | Audio format name or file extension | `opus`, `flac` |

#### Template Examples

* **Default Hierarchy** (Artist / Album (Year) / Track - Title):
  ```toml
  path_template = "{artist}/{album} ({date})/{track:02d} - {title}.opus"
  # => Daft Punk/Discovery (2001)/03 - Digital Love.opus
  ```

* **By Genre** (Genre / Artist / Album (Year) / Track - Title):
  ```toml
  path_template = "{genre}/{artist}/{album} ({year})/{track:02d} - {title}.opus"
  # => French House/Daft Punk/Discovery (2001)/03 - Digital Love.opus
  ```

* **Alphabetical Index (A-Z)** (Ideal for large libraries with hundreds of artists):
  ```toml
  path_template = "{initial}/{artist}/{album} ({year})/{track:02d} - {title}.opus"
  # => D/Daft Punk/Discovery (2001)/03 - Digital Love.opus
  ```

* **Decades Hierarchy** (Decade / Artist - Album / Track - Title):
  ```toml
  path_template = "{decade}/{artist} - {album}/{track:02d} - {title}.opus"
  # => 2000s/Daft Punk - Discovery/03 - Digital Love.opus
  ```

* **Flat by Artist** (No album subfolders):
  ```toml
  path_template = "{artist}/{track:02d} - {title}.opus"
  # => Daft Punk/03 - Digital Love.opus
  ```

* **Explicit Collaborator Credit in Filename**:
  ```toml
  path_template = "{artist}/{album} ({year})/{track:02d} - {track_artist} - {title}.opus"
  # => Daft Punk/Random Access Memories (2013)/08 - Daft Punk feat. Pharrell Williams - Get Lucky.opus
  ```

---

### Built-in Organization Behaviors

In addition to `path_template`, Apolo provides specialized organization rules that keep your library cohesive:

#### 1. Grouping Standalone Singles (`group_singles`)
When enabled (`true`), songs that belong to a single release rather than a full album are grouped into a dedicated `Singles` directory under the artist:
```text
~/Music/Apolo/Daft Punk/Singles/Get Lucky (2013).opus
```
This prevents single-track album folders from cluttering your filesystem.

#### 2. Compilations and Soundtracks (`various_artists_folder`)
When enabled (`true`), compilation albums featuring tracks by various artists (or tagged with `compilation = 1`) are unified under a common root directory:
```text
~/Music/Apolo/Various Artists/Drive OST (2011)/01 - Kavinsky - Nightcall.opus
```
This keeps guest artists from creating dozens of single-track folders in your library.

#### 3. Multi-Disc Albums (`multi_disc_folder`)
Controls how multi-CD box sets and double albums are nested:
* `multi_disc_folder = true`:
  ```text
  ~/Music/Apolo/The Beatles/The White Album (1968)/Disc 01/01 - Back in the U.S.S.R..opus
  ~/Music/Apolo/The Beatles/The White Album (1968)/Disc 02/01 - Birthday.opus
  ```
* `multi_disc_folder = false`:
  ```text
  ~/Music/Apolo/The Beatles/The White Album (1968)/1-01 - Back in the U.S.S.R..opus
  ~/Music/Apolo/The Beatles/The White Album (1968)/2-01 - Birthday.opus
  ```

#### 4. File Collision Strategy (`collision_strategy`)
Determines how Apolo behaves if a file already exists at the destination path:
* `"skip"` (default): Safely leaves the existing file untouched and preserves the source.
* `"rename"`: Automatically creates a numbered copy (e.g. `Song (1).opus`).
* `"overwrite"`: Replaces the existing file with the newly processed track.

---

### Typographic & Accent Resiliency

Apolo actively prevents folder fragmentation:
* **Accent Normalization**: Tracks by `Rosalía` will match an existing `Rosalia/` folder.
* **Symbol and Case Insensitivity**: Bands with punctuation (e.g. `C.R.O`, `C.R.O.`, `FRO!`, `Fro!`) are resolved to the same directory automatically.

---

### Applying Organization Changes (`apolo reorganize`)

If you modify your `path_template` or change organization settings in `config.toml`, you can re-sort existing files across your library in seconds:

```bash
# 1. Preview changes safely without moving files
apolo reorganize --dry-run

# 2. Apply reorganizations
apolo reorganize
```

---

## Next Steps

* Master the command suite: [CLI Reference & Workflows](02-cli-reference-and-workflows.md)
* Set up terminal file manager shortcuts: [Yazi Integration](05-yazi-integration.md)
* Connect your browser for 1-click downloads: [Browser Extension](06-browser-extension.md)
