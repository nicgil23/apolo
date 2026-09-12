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
