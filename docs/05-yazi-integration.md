# Yazi File Manager Integration

[Yazi](https://github.com/sxyazi/yazi) is a blazing-fast terminal file manager written in Rust. Apolo integrates natively into Yazi, turning it into a complete visual music management workstation with custom openers and keybindings.

---

## 1. Opener Configuration (`yazi.toml`)

Add the Apolo opener and mime rule to your `~/.config/yazi/yazi.toml`:

```toml
[opener]
# Quick metadata preview opener
info = [
    { run = 'clear; apolo info "$@"; echo "Press enter to exit"; read _', block = true, desc = "Show metadata", for = "unix" },
]

# Tag & organize opener
apolo = [
    { run = 'apolo process "$@"', block = true, desc = "Tag & organize with Apolo" },
]

[open]
rules = [
    # Allow opening media files directly with Apolo
    { mime = "{audio,video}/*", use = [ "play", "apolo", "info", "reveal" ] },
]
```

When you press <kbd>o</kbd> or <kbd>Enter</kbd> on any audio file or folder in Yazi, you can now choose **Tag & organize with Apolo** or **Show metadata**.

---

## 2. Keymap Configuration (`keymap.toml`)

Add Apolo's dedicated command palette under the prefix key <kbd>A</kbd> in `~/.config/yazi/keymap.toml`:

```toml
[mgr]
prepend_keymap = [
    # Quick Navigation
    { on = [ "g", "a" ], run = "cd ~/Music/Apolo", desc = "Go to ~/Music/Apolo" },
    { on = [ "g", "m" ], run = "cd ~/Music",       desc = "Go to ~/Music" },

    # Apolo Music Suite Palette (Prefix: A)
    { on = [ "A", "t" ], run = 'shell --block "apolo process \"$@\"; echo \"Press enter to exit\"; read _"',    desc = "Apolo: Process & tag files" },
    { on = [ "A", "T" ], run = 'shell --block "apolo process -i \"$@\"; echo \"Press enter to exit\"; read _"', desc = "Apolo: Interactive tagging" },
    { on = [ "A", "m" ], run = 'shell --block "apolo info \"$@\"; echo \"Press enter to exit\"; read _"',       desc = "Apolo: Inspect metadata" },
    { on = [ "A", "d" ], run = 'shell --block --interactive "apolo download "',                                 desc = "Apolo: Download from URL" },
    { on = [ "A", "i" ], run = 'shell --block "apolo inbox; echo \"Press enter to exit\"; read _"',              desc = "Apolo: Process inbox" },
    { on = [ "A", "r" ], run = 'shell --block "apolo reorganize \"$@\"; echo \"Press enter to exit\"; read _"', desc = "Apolo: Reorganize library" },
    { on = [ "A", "g" ], run = 'shell --block "apolo gain \"$@\"; echo \"Press enter to exit\"; read _"',       desc = "Apolo: ReplayGain normalizer" },
    { on = [ "A", "f" ], run = 'shell --block "apolo identify \"$@\"; echo \"Press enter to exit\"; read _"',   desc = "Apolo: Identify (AcoustID)" },
    { on = [ "A", "D" ], run = 'shell --block "apolo doctor; echo \"Press enter to exit\"; read _"',            desc = "Apolo: Doctor (Diagnostics)" },
    { on = [ "A", "c" ], run = 'shell --block "apolo cover extract \"$@\"; echo \"Press enter to exit\"; read _"', desc = "Apolo: Extract cover art" },
    { on = [ "A", "C" ], run = 'shell --block --interactive "apolo cover embed \"$@\" --cover "',              desc = "Apolo: Embed custom cover" },
    { on = [ "A", "e" ], run = 'shell --block --interactive "apolo edit \"$@\" "',                              desc = "Apolo: Batch edit tags" },
    { on = [ "A", "p" ], run = 'shell --block --interactive "apolo playlist "',                                 desc = "Apolo: Smart playlists" },
    { on = [ "A", "w" ], run = 'shell --block "apolo watch; echo \"Press enter to exit\"; read _"',             desc = "Apolo: Watch inbox daemon" },
    { on = [ "A", "h" ], run = 'shell --block "apolo config; echo \"Press enter to exit\"; read _"',            desc = "Apolo: Show configuration" },
]
```

---

## 3. Keyboard Shortcut Cheatsheet

| Shortcut | Action | Description |
| :--- | :--- | :--- |
| <kbd>g</kbd> <kbd>a</kbd> | Jump to Library | Instantly navigate to `~/Music/Apolo` |
| <kbd>g</kbd> <kbd>m</kbd> | Jump to Music | Instantly navigate to `~/Music` |
| <kbd>A</kbd> <kbd>t</kbd> | **Tag & Process** | Transcode, fetch tags, embed lyrics/cover for highlighted/selected items |
| <kbd>A</kbd> <kbd>T</kbd> | **Interactive Tag** | Review and select candidates interactively before writing |
| <kbd>A</kbd> <kbd>m</kbd> | **Inspect Metadata** | View technical specs, tags, and art info for hovered track |
| <kbd>A</kbd> <kbd>d</kbd> | **Download URL** | Prompts for a YouTube/SoundCloud URL and begins download |
| <kbd>A</kbd> <kbd>i</kbd> | **Process Inbox** | Ingests all songs waiting in `~/Music/Inbox` |
| <kbd>A</kbd> <kbd>r</kbd> | **Reorganize** | Re-sorts selected directory according to library path template |
| <kbd>A</kbd> <kbd>g</kbd> | **Apply Gain** | Computes and tags EBU R128 loudness / ReplayGain |
| <kbd>A</kbd> <kbd>f</kbd> | **AcoustID** | Fingerprints untagged tracks by waveform |
| <kbd>A</kbd> <kbd>D</kbd> | **Run Doctor** | Executes health audit and diagnostics across your collection |
| <kbd>A</kbd> <kbd>c</kbd> | **Extract Cover** | Extracts embedded artwork as `cover.jpg` |
| <kbd>A</kbd> <kbd>C</kbd> | **Embed Cover** | Prompts for image path and embeds it across selected tracks |
| <kbd>A</kbd> <kbd>e</kbd> | **Edit Tags** | Prompts for tag replacement options |
| <kbd>A</kbd> <kbd>p</kbd> | **Playlists** | Smart M3U8 generator prompt |
| <kbd>A</kbd> <kbd>w</kbd> | **Start Watcher** | Runs inbox watcher daemon |
| <kbd>A</kbd> <kbd>h</kbd> | **Config** | Displays active configuration and environment |
