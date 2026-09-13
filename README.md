# Apolo

A powerful, modern CLI tool written in **Python 3.14** for downloading, tagging with rich metadata, fetching synced lyrics, and organizing music into your library.

---

## Features

- **High-Quality Audio Downloads**: Downloads songs from **YouTube** and **SoundCloud** using `yt-dlp` in `.opus` codec at the highest VBR quality (`quality = 0`).
- **Comprehensive Metadata Tagging (`METADATOS_BIBLIOTECA`)**:
  - `title`, `artist`, `album_artist`, `album`
  - `track_number`, `track_total`, `disc_number`, `disc_total`
  - `date`, `genre`, `compilation`
  - `cover_art` (Embedded high-res album art via FLAC picture block in Vorbis Comments)
  - Multi-source provider aggregation (iTunes Search API, Deezer API, MusicBrainz) without requiring API keys.
- **Synchronized Lyrics**: Fetches timestamped synced lyrics (`[mm:ss.xx]`) from public APIs (LRCLIB), embedding them in the Opus Vorbis comments and saving sidecar `.lrc` files.
- **Automated Library Organization**:
  Automatically organizes tracks into:
  ```text
  /home/hypr/Music/Apolo/{artist}/{album or single name} ({date release})/{song number} - {song name}.opus
  ```
- **Batch Local Processing**: Process untagged audio files or folders (e.g., `~/Music/Inbox`) to convert, tag, fetch lyrics, and place them into the library automatically.
- **Yazi File Manager Integration**: Seamlessly integrated with Yazi via custom openers and keybindings.

---

## Installation & Requirements

Requirements:
- Python >= 3.11 (Python 3.14 recommended)
- `ffmpeg`
- `yt-dlp`

Install in editable mode:
```bash
pip install -e . --break-system-packages
```

---

## CLI Usage

### Download from YouTube / SoundCloud
```bash
apolo download "https://www.youtube.com/watch?v=5NV6Rdv1a3I"
# or alias
adl "https://soundcloud.com/artist/track"
```

### Import from Spotify / Deezer / Apple Music (`apolo import`)
Download full playlists or albums with official metadata and auto-generated `.m3u8` playlists:
```bash
# Import a Spotify playlist
apolo import "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"

# Import a Deezer album
apolo import "https://www.deezer.com/album/302127"

# Import an Apple Music album or track
apolo import "https://music.apple.com/us/album/random-access-memories/636988822"
```

### Process Local Files or Folders
```bash
# Tag and organize a specific file
apolo process ~/Downloads/song.opus

# Tag and organize an entire directory
apolo process ~/Downloads/unorganized_album/
```

### Inspect Track Metadata
```bash
apolo info ~/Music/Apolo/Artist/Album/01\ -\ Track.opus
```

### Dry-Run / Preview Mode
Preview transcoding, tag matching, and destination paths without writing to disk:
```bash
apolo process ~/Downloads/album/ --dry-run
apolo reorganize --dry-run
```

### Quick CLI Metadata Editing (`apolo set`)
Update specific tags, embed custom cover art, and optionally reorganize:
```bash
# Update title and year
apolo set "song.opus" --title "One More Time" --year 2001

# Update album tags and auto-relocate to proper library folder
apolo set "album_folder/" --genre "Synthwave" --album-artist "Kavinsky" --reorganize

# Embed custom high-res album cover
apolo set "song.opus" --cover ~/Downloads/cover.jpg
```

### Batch Text & RegEx Editing (`apolo edit`)
Clean up unwanted strings or patterns in titles, artists, or albums in bulk:
```bash
# Clean YouTube video suffixes from titles
apolo edit "folder/" --regex-title "\s*[\(\[][^)\]]*(Official|Video|Lyrics)[^)\]]*[\)\]]" ""

# Replace text in album names
apolo edit "folder/" --replace-album "Old Album Name" "New Album Name" --reorganize
```

### Library Health & Diagnostics (`apolo doctor`)
Audit your collection for duplicates, missing album tracks, missing lyrics, and low-res covers:
```bash
# General health score and audit
apolo doctor

# Specific audits
apolo doctor --duplicates
apolo doctor --missing-tracks
apolo doctor --missing-lyrics

# Automated batch repairs
apolo doctor --repair-lyrics    # Fetch missing synced lyrics from LRCLIB
apolo doctor --repair-covers    # Fetch missing HD covers from Deezer/iTunes
```

### Smart M3U8 Playlist Management (`apolo playlist`)
Create dynamic playlists, auto-repair broken paths, and export to external devices (DAP/USB):
```bash
# List existing playlists and link integrity
apolo playlist list

# Create smart playlists dynamically by metadata filters
apolo playlist create "Synthwave 80s" --genre "Synthwave" --year "1980..1989"
apolo playlist create "Soulseek Gems" --origin "soulseek"
apolo playlist create "Daft Punk Hits" --artist "Daft Punk"

# Auto-repair broken file paths after library reorganizations
apolo playlist repair

# Export playlist and audio files to USB drive or DAP
apolo playlist export "Roadtrip" /media/usb/Music/
```

### EBU R128 & ReplayGain Normalization (`apolo gain`)
Analyze audio loudness using `ffmpeg ebur128` and write standard `R128_TRACK_GAIN` and `REPLAYGAIN` tags:
```bash
# Analyze and tag an album against standard -18 LUFS (Opus / ReplayGain 2.0)
apolo gain ~/Music/Apolo/Daft\ Punk/

# Analyze against broadcast standard -23 LUFS
apolo gain ~/Music/Apolo/ --target-lufs -23
```

### Background Inbox Watcher Daemon (`apolo watch`)
Monitor `~/Music/Inbox` continuously in the background, debouncing active downloads and sending desktop notifications (`notify-send`):
```bash
# Run watcher daemon
apolo watch

# Watch a custom folder (e.g. Soulseek downloads)
apolo watch --dir ~/Downloads/Soulseek/
```

### Cover Art Management & Extraction (`apolo cover`)
Extract embedded covers as `cover.jpg` / `folder.jpg` for media servers or embed custom covers:
```bash
# Extract embedded covers to cover.jpg in each album directory
apolo cover extract ~/Music/Apolo/

# Extract as folder.jpg
apolo cover extract ~/Music/Apolo/ --name folder.jpg

# Embed high-res cover art across all album tracks
apolo cover set ~/Music/Apolo/Justice/Cross\ \(2007\)/ ~/Downloads/justice_hd.jpg
```

### Lossless Preservation / Hybrid FLAC Library (`--keep-lossless`)
Preserve high-resolution FLAC files directly without transcoding down to Opus, with full Vorbis Comments and embedded artwork:
```bash
# Process a FLAC album preserving lossless format
apolo process ~/Downloads/flac_album/ --keep-lossless

# Process inbox keeping FLACs intact
apolo inbox --keep-lossless
```

### Interactive Metadata Selector (`--interactive` / `-i`)
Review ranked candidate matches from Deezer, iTunes, and MusicBrainz before applying, with support for manual query refinement:
```bash
# Interactively select metadata for local files
apolo process ~/Downloads/unorganized/ --interactive

# Interactively match downloaded tracks
apolo download "https://youtube.com/watch?v=..." -i
```

### Acoustic Fingerprinting (`apolo identify`)
Identify completely untagged songs by their actual audio waveform using Chromaprint (`fpcalc`) and the AcoustID database:
```bash
# Identify untagged tracks
apolo identify ~/Downloads/track01.mp3

# Identify, fetch lyrics, and organize directly into the library
apolo identify ~/Downloads/mystery_album/ --apply
```

### Process Inbox
Drop songs into `~/Music/Inbox` and run:
```bash
apolo inbox
```

### View Configuration
```bash
apolo config
```

---

## Configuration (`~/.config/apolo/config.toml`)

```toml
[directories]
library_dir = "~/Music/Apolo"
inbox_dir = "~/Music/Inbox"
temp_dir = "~/.cache/apolo/temp"

[organization]
path_template = "{artist}/{album} ({date})/{track:02d} - {title}.opus"
save_lrc_file = true
embed_cover_art = true
max_cover_size = 1400

[downloader]
audio_format = "opus"
audio_quality = "0"
concurrent_downloads = 3

[providers]
prefer_deezer = true
prefer_itunes = true
prefer_musicbrainz = true
synced_lyrics_only = true
```

---

## Yazi Integration

In **Yazi**:
- Press `A` then `t`: Tag and organize selected audio file(s) or directory with Apolo.
- Press `A` then `m`: Show detailed metadata for selected audio file.
- Press `A` then `d`: Download from URL interactively with Apolo.
- Press `A` then `i`: Process `~/Music/Inbox` folder.
- Press `g` then `a`: Go to `~/Music/Apolo` folder.
- Press `g` then `m`: Go to `~/Music` folder.
- Or select an audio file and open it with the `apolo` opener.
