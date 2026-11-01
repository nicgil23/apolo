# CLI Reference & Workflows

Apolo provides a fast, rich terminal interface powered by [Typer](https://typer.tiangolo.com/) and [Rich](https://rich.readthedocs.io/).

---

## Command Overview

| Command | Aliases | Description |
| :--- | :--- | :--- |
| [`apolo download`](#apolo-download) | `adl` | Download audio from YouTube/SoundCloud, transcode, tag, and organize |
| [`apolo process`](#apolo-process) | `tag` | Transcode, fetch metadata/lyrics, and sort local audio files or folders |
| [`apolo inbox`](#apolo-inbox) | - | Process all files currently staged in `~/Music/Inbox` |
| [`apolo reorganize`](#apolo-reorganize) | `tidy` | Re-sort library tracks according to updated naming conventions/tags |
| [`apolo set`](#apolo-set) | - | In-place metadata tagger and cover art embedder |
| [`apolo edit`](#apolo-edit) | - | Batch search-and-replace or regex cleaning for tags |
| [`apolo info`](#apolo-info) | `inspect` | Pretty-print Vorbis/FLAC metadata, audio specs, and embedded art |
| [`apolo gain`](#apolo-gain) | - | Analyze EBU R128 loudness and write ReplayGain tags |
| [`apolo identify`](#apolo-identify) | - | Identify untagged audio via Chromaprint waveform and AcoustID |
| [`apolo doctor`](#apolo-doctor) | - | Audit library health, find duplicates/anomalies, and run repairs |
| [`apolo playlist`](#apolo-playlist) | - | Smart M3U8 generation, path repair, and DAP/USB exporter |
| [`apolo cover`](#apolo-cover) | - | Extract embedded album art to disk or batch embed new artwork |
| [`apolo watch`](#apolo-watch) | `daemon` | Background file watcher for automatic inbox processing |
| [`apolo serve`](#apolo-serve) | - | Local REST API daemon for browser extensions and external integrations |
| [`apolo config`](#apolo-config) | - | Print active configuration and system environment status |

---

## Global Workflow Flags

Many commands support standard workflow flags:

* `--dry-run` / `-n`: Simulate actions (renaming, tagging, moving) without writing any changes to disk.
* `--interactive` / `-i`: Display ranked metadata candidate matches from Deezer, iTunes, and MusicBrainz, allowing manual selection or custom query overrides.
* `--keep-lossless` / `--no-keep-lossless`: Override configuration to force preserving FLAC or converting to Opus.
* `--to-opus`: Convenient shortcut for `--no-keep-lossless` to transcode FLAC down to Opus.

---

## Detailed Command Documentation

### `apolo download`
Alias: `adl`

Downloads audio from YouTube, YouTube Music, or SoundCloud using `yt-dlp`, converts to high-quality Opus (or FLAC if `--keep-lossless` and source allows), queries metadata providers, embeds cover art and synchronized lyrics, and sorts the track into your library.

```bash
apolo download <URL> [OPTIONS]
```

**Options:**
* `-i`, `--interactive`: Interactively select the best metadata match from ranked provider results.
* `--keep-lossless`: Preserve original lossless stream without converting to Opus.
* `-o`, `--output-dir PATH`: Override default destination directory.

**Examples:**
```bash
# Fast automated download
apolo download "https://www.youtube.com/watch?v=5NV6Rdv1a3I"

# Interactive candidate selection
apolo download -i "https://soundcloud.com/artist/obscure-remix"
```

---

### `apolo process`
Alias: `tag`

Ingests local audio files or folders. For each file, Apolo transcodes the audio, fetches metadata from providers, embeds lyrics and artwork, and places it into `~/Music/Apolo/{artist}/{album} ({year})/{track} - {title}.opus`.

```bash
apolo process <PATH> [OPTIONS]
```

**Options:**
* `-i`, `--interactive`: Review candidate matches before applying.
* `--keep-lossless` / `--no-keep-lossless`: Preserve FLAC files or force Opus conversion (overrides config).
* `--to-opus`: Force transcoding FLAC down to Opus.
* `-n`, `--dry-run`: Preview destination paths and tags without touching files.

**Examples:**
```bash
# Process a single downloaded file
apolo process ~/Downloads/track.m4a

# Process a newly downloaded album folder
apolo process ~/Downloads/RandomAlbum/

# Preview changes safely
apolo process ~/Downloads/RandomAlbum/ --dry-run
```

---

### `apolo inbox`

A shortcut that processes all supported audio files currently inside `inbox_dir` (default: `~/Music/Inbox`).

```bash
apolo inbox [OPTIONS]
```

**Options:**
* `-i`, `--interactive`: Interactive match review.
* `--keep-lossless` / `--no-keep-lossless`: Keep FLAC files lossless or force Opus conversion.
* `--to-opus`: Force transcoding FLAC down to Opus.
* `-n`, `--dry-run`: Dry-run simulation.

---

### `apolo reorganize`
Alias: `tidy`

Scans your existing library (or a specific subdirectory) and moves/renames files according to the active `path_template` configuration (e.g., if you fixed metadata or changed folder structures).

```bash
apolo reorganize [PATH] [OPTIONS]
```

See [Library Organization & Path Template Syntax](01-installation-and-setup.md#4-library-organization--path-template-syntax) for details on custom path templates and organization flags.

**Options:**
* `-n`, `--dry-run`: Preview relocation plan without moving files.

---

### `apolo set`

Quickly update individual tag fields directly on one or more files or directories.

```bash
apolo set <TARGET> [OPTIONS]
```

**Options:**
* `--title TEXT`: Update track title.
* `--artist TEXT`: Update track artist.
* `--album-artist TEXT`: Update album artist.
* `--album TEXT`: Update album name.
* `--year INTEGER`: Update release year / date.
* `--genre TEXT`: Update genre tag.
* `--track INTEGER`: Set track number.
* `--total-tracks INTEGER`: Set total track count.
* `--disc INTEGER`: Set disc number.
* `--total-discs INTEGER`: Set total disc count.
* `--cover PATH`: Embed image file as cover art.
* `-r`, `--reorganize`: Automatically move file to its correct path after updating tags.
* `-n`, `--dry-run`: Preview tag changes without saving.

**Examples:**
```bash
# Fix year and genre
apolo set "song.opus" --year 1997 --genre "French House"

# Set album artist and relocate
apolo set "folder/" --album-artist "Daft Punk" -r

# Embed a custom cover image
apolo set "song.opus" --cover ~/Pictures/custom_cover.jpg
```

---

### `apolo edit`

Perform batch string replacements or regular expression cleanup across track titles, artists, or album names.

```bash
apolo edit <TARGET> [OPTIONS]
```

**Options:**
* `--replace-title OLD NEW`: Simple substring replacement in titles.
* `--replace-artist OLD NEW`: Substring replacement in artist names.
* `--replace-album OLD NEW`: Substring replacement in album names.
* `--regex-title PATTERN REPL`: Python regex replacement in titles.
* `--regex-artist PATTERN REPL`: Python regex replacement in artists.
* `--regex-album PATTERN REPL`: Python regex replacement in albums.
* `-r`, `--reorganize`: Re-sort files into their proper folders after editing.
* `-n`, `--dry-run`: Preview matched strings and proposed replacements.

**Examples:**
```bash
# Strip annoying YouTube video titles like "(Official Video)", "[Lyric Video]"
apolo edit "folder/" --regex-title "\s*[\(\[][^)\]]*(Official|Video|Audio|HD|Lyrics)[^)\]]*[\)\]]" ""

# Fix misspelled artist name across an entire collection
apolo edit ~/Music/Apolo/ --replace-artist "Dafl Punk" "Daft Punk" -r
```

---

### `apolo info`
Alias: `inspect`

Inspects an audio file and prints a formatted summary of its Vorbis comments/tags, technical stream attributes (sample rate, channels, bitrate), and embedded cover art details.

```bash
apolo info <FILE_PATH>
```

---

### `apolo gain`

Calculates integrated loudness in LUFS according to **ITU-R BS.1770 / EBU R128** via `ffmpeg` and writes standard tags (`R128_TRACK_GAIN` and `REPLAYGAIN_TRACK_GAIN` / `REPLAYGAIN_TRACK_PEAK`).

```bash
apolo gain <PATH> [OPTIONS]
```

**Options:**
* `--target-lufs FLOAT`: Target loudness level in LUFS (default: `-18.0` for Opus/ReplayGain 2.0; `-23.0` for broadcast).

---

### `apolo identify`

Uses Chromaprint (`fpcalc`) to compute an acoustic fingerprint of the audio waveform and queries the AcoustID database. Essential for recovering metadata for files with missing or corrupted tags.

```bash
apolo identify <PATH> [OPTIONS]
```

**Options:**
* `--apply`: Automatically fetch full metadata, embed lyrics/cover, and move to library.
* `-i`, `--interactive`: Interactively choose between AcoustID candidates.
* `--keep-lossless`: Retain lossless FLAC format when applying.

---

### `apolo doctor`

Comprehensive health audit and repair suite for your music collection. Diagnoses duplicates, missing tracks in albums, absent lyrics, and non-standard genres.

See [Library Doctor & Repairs](03-library-doctor.md) for full documentation and repair options.

---

### `apolo playlist`

Create smart M3U8 playlists based on metadata criteria, repair paths after library restructuring, and export playlists and media files to external drives.

See [Smart Playlists](07-smart-playlists.md) for full documentation.

---

### `apolo cover`

Manage album artwork directly on files.

```bash
# Extract embedded covers to cover.jpg (or custom name)
apolo cover extract <TARGET> [--name cover.jpg]

# Embed an image file into all tracks in a folder
apolo cover embed <TARGET> --cover <IMAGE_PATH>
```

---

### `apolo watch`
Alias: `daemon`

Runs a lightweight filesystem watcher on your inbox directory (`~/Music/Inbox`). When a download or file drop completes (debounced to avoid partial writes), Apolo automatically transcodes, tags, and organizes the track, sending a desktop notification via `notify-send`.

```bash
apolo watch [--dir PATH]
```

---

### `apolo serve`

Runs the local FastAPI HTTP/REST server on `http://127.0.0.1:4533`. Used by the [Browser Extension](06-browser-extension.md) to receive download requests directly from YouTube and YouTube Music.

```bash
apolo serve [--host 127.0.0.1] [--port 4533]
```
