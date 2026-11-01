# Smart Playlists & DAP Export

Apolo features an intelligent M3U8 playlist management engine designed to keep your playlists synchronized, dynamically generated, and portable across portable audio players (DAPs), car audio units, and mobile devices.

---

## 1. Creating Dynamic Smart Playlists

Unlike static playlists that require manual track curation, Apolo can query your collection's Vorbis Comment / FLAC metadata to generate dynamic playlists instantly:

```bash
apolo playlist create <NAME> [OPTIONS]
```

### Options:
* `--genre TEXT`: Filter by genre (supports case-insensitive fuzzy match).
* `--year TEXT`: Filter by single year (`2021`) or date range (`1980..1989`).
* `--artist TEXT`: Filter by artist or album artist.
* `--origin TEXT`: Filter by acquisition source (e.g. `youtube`, `soulseek`).

### Examples:
```bash
# All Synthwave tracks
apolo playlist create "Synthwave Hits" --genre "Synthwave"

# Golden era 80s music
apolo playlist create "Eighties Classics" --year "1980..1989"

# Artist-focused playlist
apolo playlist create "Justice Essentials" --artist "Justice"
```

Playlists are saved in UTF-8 M3U8 format with standard `#EXTINF` metadata records inside `~/Music/Apolo/Playlists/` (or configured playlist directory).

---

## 2. Inspecting Playlists & Link Integrity

To view all existing playlists along with track counts, total duration, and link validity:

```bash
apolo playlist list
```

Sample output:
```text
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
┃ Playlist           ┃ Tracks ┃ Duration ┃ Integrity      ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
│ French House.m3u8  │ 42     │ 2h 45m   │ [OK] 100% Valid│
│ Workout Mix.m3u8   │ 18     │ 1h 12m   │ [!] 2 Broken   │
└────────────────────┴────────┴──────────┴────────────────┘
```

---

## 3. Auto-Repairing Broken Paths (`apolo playlist repair`)

When you rename artists, clean tags with `apolo edit`, or reorganize your library with `apolo reorganize`, traditional playlists break because hardcoded file paths point to the old locations.

Apolo solves this automatically:

```bash
apolo playlist repair
```

### How `playlist repair` Works:
1. Parses each track entry in all `.m3u8` files.
2. If the target file no longer exists at that path, extracts the track's metadata signature (`Artist`, `Title`, `Album`).
3. Performs a fuzzy lookup against current files in `library_dir`.
4. Updates the playlist file with the verified new path without altering playback order.

---

## 4. Exporting to DAPs and USB Drives (`apolo playlist export`)

Copying an `.m3u8` playlist directly to a USB stick, SD card, or dedicated Digital Audio Player (e.g. Sony Walkman, FiiO, Hiby, Astell&Kern) fails because paths refer to your host computer's home directory.

The `export` command copies both the playlist and the audio tracks, adjusting paths to be strictly relative:

```bash
apolo playlist export <PLAYLIST_NAME> <DESTINATION_DIRECTORY>
```

### Example:
```bash
# Mount external USB drive
apolo playlist export "French House" /run/media/hypr/WALKMAN/Music/
```

### What Happens:
1. Copies all audio files into a dedicated subfolder on the external drive:
   ```text
   /run/media/hypr/WALKMAN/Music/French House/01 - One More Time.opus
   /run/media/hypr/WALKMAN/Music/French House/02 - Aerodynamic.opus
   ```
2. Copies matching `.lrc` lyrics files (if present).
3. Writes a portable `.m3u8` playlist with relative paths, ensuring immediate plug-and-play playback on your device.
