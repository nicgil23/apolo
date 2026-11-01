# Audio Transcoding & Tagging Specs

Apolo is engineered for pristine audio quality and rich metadata tagging, treating your collection with audiophile standards.

---

## 1. Opus Transcoding Architecture

By default, Apolo standardizes audio into the modern **Opus** format (`.opus` container using Ogg Vorbis Comment metadata).

### Why Opus?
* **Superior Perceptual Quality**: Opus outperforms MP3, AAC, and Ogg Vorbis at equivalent bitrates. At ~160–256 kbps VBR, Opus achieves transparent fidelity indistinguishable from uncompressed master audio.
* **Open Standard & Efficiency**: Low computational overhead, minimal container bloat, native playback support across all modern operating systems, mobile devices, and browsers.

### Transcoder Parameters (`AudioConverter`)
When transcoding lossy sources or non-FLAC files, Apolo passes optimal parameters to FFmpeg:

```bash
ffmpeg -i input.ext -vn -c:a libopus -b:a 256k -vbr on -compression_level 10 output.opus
```

* **Codec**: `libopus`
* **Bitrate**: `256k VBR` (Variable Bitrate dynamic allocation)
* **Sample Rate**: Native 48,000 Hz resampling (internal clock of Opus)
* **Compression Level**: `10` (maximum algorithmic optimization)

---

## 2. Hybrid Lossless Architecture (`preserve_lossless`)

For collectors with high-resolution FLAC files, transcoding down to Opus is often undesirable. Apolo provides a **Hybrid Library** model that can be configured permanently or controlled on demand:

### Permanent Configuration (`config.toml`)
To keep all FLAC files in your collection permanently without lossy transcoding:

```toml
[downloader]
preserve_lossless = true
```

Whenever `preserve_lossless = true`, all commands (`apolo inbox`, `apolo process`, and the `apolo watch` daemon) automatically preserve FLAC files in pristine bit-perfect quality.

### Command-Line Overrides

You can override your global setting for specific albums or runs:

```bash
# Force preserving FLAC (even if preserve_lossless = false in config.toml)
apolo process ~/Downloads/hires_album/ --keep-lossless

# Force transcoding FLAC down to Opus (even if preserve_lossless = true in config.toml)
apolo process ~/Downloads/hires_album/ --to-opus
# or
apolo process ~/Downloads/hires_album/ --no-keep-lossless
```

When lossless preservation is active:
* If input is `.flac`, no audio transcoding occurs; the bit-perfect FLAC audio stream is preserved.
* Vorbis Comment tags are written directly to the FLAC container.
* High-res cover art is embedded using native `METADATA_BLOCK_PICTURE`.
* Filename is formatted as `{track:02d} - {title}.flac` inside your library structure.

---

## 3. Metadata Tagging Architecture

Apolo writes standard tags (`METADATOS_BIBLIOTECA`) recognized by modern media players (Foobar2000, Navidrome, Jellyfin, Apple Music, MPD, Symfonium):

| Tag Field | Vorbis Comment Key (Opus/FLAC) | Description |
| :--- | :--- | :--- |
| **Title** | `TITLE` | Track name |
| **Artist** | `ARTIST` | Primary performing artist |
| **Album Artist** | `ALBUMARTIST` | Primary album artist (prevents fragmented album view) |
| **Album** | `ALBUM` | Album / EP / Single title |
| **Track Number** | `TRACKNUMBER` | Zero-padded track position |
| **Track Total** | `TRACKTOTAL` | Total tracks on album |
| **Disc Number** | `DISCNUMBER` | Media disc index |
| **Disc Total** | `DISCTOTAL` | Total media discs |
| **Date / Year** | `DATE` | Release date (e.g. `2024-05-10` or `2024`) |
| **Genre** | `GENRE` | Musical genre taxonomy |
| **Lyrics** | `LYRICS` | Synchronized timestamped lyrics (`[mm:ss.xx]`) |
| **Cover Art** | `METADATA_BLOCK_PICTURE` | Base64-encoded FLAC picture block (PNG/JPEG) |

### Multi-Provider Aggregation
Apolo does not require private API keys. It queries three public databases simultaneously:
1. **Deezer API**: Fast lookup, standardized genre tagging, 1400x1400 artwork.
2. **Apple iTunes Search API**: High-resolution album artwork (up to 3000x3000px), clean clean tracklists.
3. **MusicBrainz**: Exhaustive open discography reference for edge releases and collaborative credits.

Candidate matches are scored based on Levenshtein distance on title, artist, and track duration.

---

## 4. Synchronized Lyrics Engine (LRCLIB)

Apolo fetches lyrics from [LRCLIB](https://lrclib.net/), the premier open-source lyrics repository.

* **Embedded Lyrics**: Synced lyrics with millisecond timestamps (`[01:23.45] ...`) are embedded directly into the `LYRICS` Vorbis Comment tag.
* **Sidecar `.lrc` Files**: If `save_lrc_file = true` in `config.toml`, a matching `.lrc` file is generated alongside the audio file (e.g. `01 - Song.opus` and `01 - Song.lrc`), ensuring compatibility with hardware DAPs and legacy players.

---

## 5. EBU R128 & ReplayGain Normalization (`apolo gain`)

To eliminate jarring volume jumps between tracks from different eras and sources, Apolo supports **ITU-R BS.1770-4 / EBU R128** loudness normalization.

```bash
# Analyze album against standard -18 LUFS (Opus / ReplayGain 2.0 standard)
apolo gain ~/Music/Apolo/Daft\ Punk/

# Analyze against broadcast standard -23 LUFS
apolo gain ~/Music/Apolo/Classical/ --target-lufs -23.0
```

### How it works:
1. Apolo feeds the audio stream through FFmpeg's `ebur128` filter to measure Integrated Loudness (LUFS) and True Peak (dBFS).
2. Computes the target gain adjustment: $\Delta \text{Gain} = \text{Target LUFS} - \text{Measured LUFS}$.
3. Writes non-destructive standard tags:
   - `R128_TRACK_GAIN` (Standard Opus integer Q7.8 format)
   - `REPLAYGAIN_TRACK_GAIN` (e.g. `-3.20 dB`)
   - `REPLAYGAIN_TRACK_PEAK` (e.g. `0.985000`)

---

## 6. Acoustic Fingerprinting (`apolo identify`)

When audio files have missing, incorrect, or gibberish tags (such as `track_01.mp3` or recordings from analog sources), text searches fail.

Apolo uses Chromaprint's `fpcalc` binary to calculate an audio waveform fingerprint and queries the [AcoustID](https://acoustid.org/) database:

```bash
# Preview AcoustID match for mystery track
apolo identify ~/Downloads/mystery.mp3

# Automatically apply tags, fetch lyrics/cover, and move to library
apolo identify ~/Downloads/mystery.mp3 --apply

# Interactively choose when multiple candidates exist
apolo identify ~/Downloads/mystery.mp3 --interactive
```
