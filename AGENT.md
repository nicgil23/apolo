# AGENT.md - AI Coding Assistant Guidelines & Repository Context

This document provides operational context, architectural principles, commands, and non-negotiable rules for AI coding assistants working in the Apolo repository.

---

## 1. Project Overview & Tech Stack

Apolo is an audiophile-grade CLI music downloader, smart tagger, and library organizer built for terminal power users.

* **Language**: Python 3.14 (compatible with >= 3.11)
* **Environment / Package Manager**: `uv`
* **CLI Framework**: Typer + Rich
* **Metadata & Audio Engine**: Mutagen (Vorbis Comment / FLAC picture blocks) + FFmpeg / ffprobe
* **Acoustic Fingerprinting**: Chromaprint (`fpcalc`) + AcoustID API
* **Public Metadata Providers**: Deezer API, Apple iTunes Search API, MusicBrainz, LRCLIB (synced lyrics)
* **Browser Extension**: Manifest V3 extension in `plugins/youtube/` communicating with `apolo serve` (FastAPI)

---

## 2. Architecture & Subpackage Map

The codebase is strictly modularized under `apolo/`. Adhere to single-responsibility boundaries:

| Subpackage | Path | Primary Responsibilities |
| :--- | :--- | :--- |
| **`apolo.audio`** | `apolo/audio/` | Low-level transcoding (`AudioConverter`), EBU R128 loudness calculation (`LoudnessScanner`, `gain.py`), and download service (`Downloader`). |
| **`apolo.tagging`** | `apolo/tagging/` | Metadata tagging (`AudioTagger`), embedded cover art extraction/injection (`CoverManager`), synchronized lyrics (`LyricsProvider`), and acoustic fingerprinting (`AcousticFingerprinter`). |
| **`apolo.library`** | `apolo/library/` | Library organization (`LibraryOrganizer`), dynamic template engine (`PathTemplateEngine`), health audit and batch repairs (`LibraryDoctor`), and smart playlists (`PlaylistManager`). |
| **`apolo.metadata`** | `apolo/metadata/` | Data classes (`TrackMetadata`), online provider clients (Deezer, iTunes, MusicBrainz, LRCLIB), genre normalization, and fuzzy candidate matching (`MetadataMatcher`). |
| **`apolo.services`** | `apolo/services/` | Long-running background daemons: `InboxWatcher` (debounced file system watcher) and `Server` (FastAPI REST server). |
| **`apolo.storage`** | `apolo/storage/` | File system path sanitization (`sanitize_filename`, `strip_accents`, `normalize_dir_key`) and state persistence. |
| **`apolo.system`** | `apolo/system/` | Host binary dependency checking (`SystemEnvironment`) for `ffmpeg`, `ffprobe`, `fpcalc`, and `notify-send`. |
| **`apolo.cli`** | `apolo/cli/` | Command registration, argument parsing, interactive menus (`candidate_selector`), and Rich UI formatting. |

---

## 3. Essential Development & Testing Commands

Always run tools through `uv` from the repository root:

* **Run complete test suite**:
  ```bash
  uv run pytest tests
  ```
* **Run specific test module**:
  ```bash
  uv run pytest tests/test_path_templates.py
  uv run pytest tests/test_lossless.py
  ```
* **Check linting & imports**:
  ```bash
  uv run ruff check .
  ```
* **Verify code formatting**:
  ```bash
  uv run ruff format --check .
  ```
* **Auto-format code**:
  ```bash
  uv run ruff format .
  uv run ruff check --fix .
  ```

---

## 4. Hard Rules & Non-Negotiable Constraints

1. **Global Git Constraints (CRITICAL)**:
   * **NEVER** run write git commands: `git commit`, `git push`, `git pull`, `git checkout`, `git switch`, or `git reset`.
   * Only read-only git inspection is permitted: `git status`, `git diff`, and `git log`.
   * All branching, staging, and commit creation must be left exclusively to the human developer.

2. **Zero Emojis in Documentation**:
   * Do not include emojis or graphical pictograms in `README.md`, `AGENT.md`, or any documentation in `docs/`. Use plain text labels (e.g. `[OK]` instead of checkmark emojis).

3. **Modern Python Typing & Style**:
   * Use Python 3.11+ native generics (`list[str]`, `dict[str, Any]`, `tuple[int, ...]`, `X | None`). Do NOT import `List`, `Dict`, `Tuple`, or `Optional` from `typing`.
   * Enforce line length limit of **100 characters** (`pyproject.toml`).
   * Preserve existing docstrings, technical comments, and typing annotations.

---

## 5. Domain Gotchas & Technical Patterns

* **Filesystem Sanitization**:
  Never strip reserved characters blindly. `sanitize_filename` maps invalid filesystem characters (`/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`) to full-width aesthetic Unicode characters (e.g. `/` -> `／`, `:` -> `：`) so track titles like *"AC/DC"* or *"Part 1: Prelude"* do not inject accidental directory separators.
* **Typographic & Case Resiliency**:
  Directory resolution uses `_resolve_case_insensitive_dir` in `LibraryOrganizer` to match existing disk folders regardless of accents (`Rosalía` vs `Rosalia`) or punctuation (`C.R.O.` vs `C.R.O`).
* **Hybrid Lossless Architecture**:
  * Default codec is Opus 256k VBR.
  * `config.downloader.preserve_lossless`: Global permanent flag in `config.toml`. If `true`, FLAC inputs are kept bit-perfect without transcoding.
  * CLI overrides: `--keep-lossless` forces FLAC preservation; `--to-opus` / `--no-keep-lossless` forces transcoding to Opus.
* **External Binary Verification**:
  Do not invoke external commands with unhandled `subprocess` calls. Verify availability using `SystemEnvironment` or `AcousticFingerprinter.is_fpcalc_available()`.
