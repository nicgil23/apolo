# Library Doctor & Maintenance

`apolo doctor` is the diagnostic and automated self-healing engine of Apolo. It audits your music collection for technical and metadata defects, computes a quantitative **Health Score**, manages intentional discography exceptions, and executes non-destructive batch repairs.

---

## 1. The Health Score

When you run `apolo doctor`, Apolo performs deep structural inspection across all tracks in `library_dir`:

```bash
apolo doctor
```

The audit evaluates:
1. **Duplicates**: Tracks with identical audio content or matching metadata signatures.
2. **Incomplete Albums**: Albums missing track numbers based on `track_total` tags (excluding controlled exceptions).
3. **Fragmented Artist Folders**: Collaborative tracks creating splintered artist directories (e.g. `Artist A feat. Artist B/` instead of `Artist A/`).
4. **Missing Lyrics**: Tracks without synchronized (`.lrc` / embedded) lyrics.
5. **Missing or Low-Res Cover Art**: Tracks without embedded artwork or below minimum resolution.
6. **Genre Consistency**: Missing or unnormalized genre tags.
7. **System Binaries**: Availability of `ffmpeg`, `ffprobe`, `fpcalc`, and `notify-send`.

The calculated **Health Score (0–100%)** gives an instant, actionable metric of collection quality.

---

## 2. Controlled Anomalies (`--control` / `--uncontrol`)

### The Incomplete Album Problem

Often, music collectors deliberately keep only favorite songs from an album (or an artist released an EP with non-consecutive track numbering). Under normal audits, these albums are flagged as "Missing Tracks", lowering your Health Score.

Apolo solves this with **Controlled Anomalies**.

### Marking an Album as Controlled

Tell Doctor that an album is intentionally partial:

```bash
# Mark by "Artist - Album" or unique substring
apolo doctor --control "Daft Punk - Tron Legacy"
```

This persistently registers the pattern in `~/.config/apolo/config.toml` under `[doctor.controlled_anomalies]`. Controlled albums:
* Are exempted from penalty in the Health Score.
* Are neatly grouped in the Controlled Anomalies table rather than flagged as defects.

### Viewing and Removing Controlled Anomalies

```bash
# View only controlled albums
apolo doctor --controlled

# Remove from exceptions (resume normal auditing)
apolo doctor --uncontrol "Daft Punk - Tron Legacy"
```

---

## 3. Targeted Diagnostic Audits

Run focused audits when inspecting specific categories of defects:

```bash
# Check only for duplicate tracks
apolo doctor --duplicates

# Inspect only incomplete albums
apolo doctor --missing-tracks

# Inspect tracks missing synchronized lyrics
apolo doctor --missing-lyrics

# Inspect tracks missing high-resolution covers
apolo doctor --missing-covers
```

---

## 4. Automated Batch Repairs

Apolo Doctor does not just report problems; it can resolve them automatically across hundreds of tracks.

> [!TIP]
> Use `--dry-run` (`-n`) on any repair command to simulate changes before writing to disk.

### A. Mass Fetch Missing Synced Lyrics
Queries LRCLIB for timestamped lyrics, embeds them into the Opus Vorbis Comment or FLAC metadata, and saves sidecar `.lrc` files:

```bash
apolo doctor --repair-lyrics
# Preview first:
apolo doctor --repair-lyrics --dry-run
```

### B. Mass Fetch High-Res Covers
Queries Deezer and iTunes APIs to retrieve 1400x1400+ album artwork and embeds it into all tracks missing covers:

```bash
apolo doctor --repair-covers
```

### C. Unify Fragmented Collaborative Folders
Identifies tracks filed under `Artist A feat. Artist B` or `Artist A & Artist B`, re-tags `album_artist` as `Artist A`, and merges the folder structure into `Artist A/`:

```bash
apolo doctor --repair-fragmented
```

### D. Fix and Normalize Genres
Audits genre tags, resolves missing tags via online provider heuristics, and standardizes casing and taxonomy:

```bash
apolo doctor --fix-genres
```

### E. Run Full Suite Repair (`--repair-all`)
Executes all repair modules in a single optimized pass:

```bash
apolo doctor --repair-all
```

---

## 5. System Binary Check

Every invocation of `apolo doctor` inspects your host environment for required helper binaries:

```text
[OK] ffmpeg: /usr/bin/ffmpeg (Transcoding, remuxing, cover embedding)
[OK] ffprobe: /usr/bin/ffprobe (Metadata & stream inspection)
[OK] fpcalc: /usr/bin/fpcalc (AcoustID waveform fingerprinting)
[OK] notify-send: /usr/bin/notify-send (Desktop notifications)
```

If a binary is missing, Doctor will suggest the exact command needed for your Linux distribution or macOS.
