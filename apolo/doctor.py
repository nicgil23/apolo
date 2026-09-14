import hashlib
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple
import mutagen
from mutagen.oggopus import OggOpus
from PIL import Image

from apolo.config import ApoloConfig, load_config
from apolo.lyrics.lrclib import LRCLIBProvider
from apolo.metadata.matcher import MetadataMatcher
from apolo.metadata.models import TrackMetadata
from apolo.pipeline import AUDIO_EXTENSIONS, ProcessingPipeline
from apolo.tagger import AudioTagger
from apolo.utils import normalize_search_string


@dataclass
class DuplicateGroup:
    artist: str
    title: str
    tracks: List[Path]
    match_type: str  # "hash" or "fuzzy_tag"


from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

@dataclass
class IncompleteAlbum:
    album_artist: str
    album_title: str
    track_total: Union[int, str]
    present_tracks: List[Any]
    missing_tracks: List[Any]
    folder: Path


@dataclass
class LibraryHealthReport:
    total_tracks: int = 0
    total_albums: int = 0
    duplicates: List[DuplicateGroup] = field(default_factory=list)
    incomplete_albums: List[IncompleteAlbum] = field(default_factory=list)
    missing_lyrics: List[Path] = field(default_factory=list)
    missing_or_lowres_covers: List[Tuple[Path, str]] = field(default_factory=list)  # (path, reason)
    missing_essential_tags: List[Tuple[Path, List[str]]] = field(default_factory=list)  # (path, missing_fields)
    fragmented_artist_folders: List[Tuple[Path, Path, str]] = field(default_factory=list)  # (fragmented_dir, target_dir, primary_name)
    health_score: float = 100.0
    lyrics_coverage: float = 100.0


class LibraryDoctor:
    def __init__(self, config: Optional[ApoloConfig] = None):
        self.config = config or load_config()
        self.pipeline = ProcessingPipeline(self.config)
        self.lyrics_provider = LRCLIBProvider(synced_only=self.config.providers.synced_lyrics_only)
        self.matcher = MetadataMatcher(self.config)

    def scan_library(
        self,
        library_dir: Optional[Path] = None,
        on_progress: Optional[Callable[[str, str], None]] = None,
    ) -> LibraryHealthReport:
        target_dir = library_dir or self.config.directories.library_dir
        report = LibraryHealthReport()

        if not target_dir.exists():
            return report

        if on_progress:
            on_progress("scanning", f"Scanning audio files in {target_dir}...")

        all_audio_files = sorted([
            p for p in target_dir.rglob("*")
            if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS and "Playlists" not in p.parts
        ])
        report.total_tracks = len(all_audio_files)

        if report.total_tracks == 0:
            return report

        # Data accumulators
        hash_map: Dict[str, List[Path]] = {}
        fuzzy_map: Dict[Tuple[str, str], List[Tuple[Path, Optional[float]]]] = {}
        albums_map: Dict[Tuple[str, str], Dict[str, any]] = {}

        for idx, file_path in enumerate(all_audio_files, 1):
            if on_progress and idx % 10 == 0:
                on_progress("auditing", f"Auditing tracks ({idx}/{report.total_tracks})...")

            info = self.pipeline.extract_file_info(file_path)
            title = info.get("title") or ""
            artist = info.get("artist") or ""
            album = info.get("album") or ""
            album_artist = info.get("album_artist") or artist
            track_num = info.get("track_number")
            track_total = info.get("track_total")
            date = info.get("date")
            genre = info.get("genre")
            duration = info.get("duration")
            cover_data = info.get("cover_art_data")

            # 1. Exact File Hash check
            try:
                with open(file_path, "rb") as f:
                    file_hash = hashlib.md5(f.read(65536)).hexdigest()
                hash_map.setdefault(file_hash, []).append(file_path)
            except Exception:
                pass

            # 2. Fuzzy metadata grouping for duplicates
            norm_title = normalize_search_string(title).lower()
            norm_artist = normalize_search_string(artist).lower()
            if norm_title and norm_artist:
                fuzzy_map.setdefault((norm_artist, norm_title), []).append((file_path, duration))

            # 3. Album completeness tracking
            norm_album = normalize_search_string(album).lower()
            norm_aa = normalize_search_string(album_artist).lower()
            disc_num = info.get("disc_number") or 1
            disc_total = info.get("disc_total")

            if norm_album and norm_aa and norm_album not in ["single", "singles", "unknown"]:
                alb_key = (norm_aa, norm_album)
                if alb_key not in albums_map:
                    albums_map[alb_key] = {
                        "album_artist": album_artist,
                        "album_title": album,
                        "discs": {},
                        "disc_totals": set(),
                        "track_totals": set(),
                        "total_files": 0,
                        "folders": set(),
                    }
                alb_entry = albums_map[alb_key]
                alb_entry["total_files"] += 1
                alb_entry["folders"].add(file_path.parent)
                if disc_total is not None:
                    alb_entry["disc_totals"].add(disc_total)
                if track_total is not None:
                    alb_entry["track_totals"].add(track_total)

                disc_entry = alb_entry["discs"].setdefault(disc_num, {"present_tracks": set(), "track_totals": set()})
                if track_num is not None:
                    disc_entry["present_tracks"].add(track_num)
                if track_total is not None:
                    disc_entry["track_totals"].add(track_total)

            # 4. Missing Lyrics audit
            has_lyrics = bool(info.get("lyrics"))
            sidecar_lrc = file_path.with_suffix(".lrc")
            if not has_lyrics and not sidecar_lrc.exists():
                report.missing_lyrics.append(file_path)

            # 5. Cover Art audit
            if not cover_data:
                report.missing_or_lowres_covers.append((file_path, "No cover art embedded"))
            else:
                try:
                    with Image.open(io.BytesIO(cover_data)) as img:
                        w, h = img.size
                        if w < 500 or h < 500:
                            report.missing_or_lowres_covers.append((file_path, f"Low resolution ({w}x{h}px)"))
                except Exception:
                    report.missing_or_lowres_covers.append((file_path, "Corrupt cover art"))

            # 6. Essential Tags audit
            missing_fields = []
            if not date:
                missing_fields.append("date/year")
            if not genre:
                missing_fields.append("genre")
            if track_num is None and norm_album not in ["single", "singles"]:
                missing_fields.append("track_number")
            if missing_fields:
                report.missing_essential_tags.append((file_path, missing_fields))

        # Deduplicate and aggregate duplicates
        seen_dup_paths: Set[Path] = set()
        for fhash, tracks in hash_map.items():
            if len(tracks) > 1:
                info = self.pipeline.extract_file_info(tracks[0])
                report.duplicates.append(
                    DuplicateGroup(
                        artist=info.get("artist") or "Unknown Artist",
                        title=info.get("title") or tracks[0].stem,
                        tracks=tracks,
                        match_type="hash",
                    )
                )
                seen_dup_paths.update(tracks)

        for (n_art, n_tit), track_tuples in fuzzy_map.items():
            if len(track_tuples) > 1:
                paths = [t[0] for t in track_tuples]
                # Filter out if already captured by hash check
                if all(p in seen_dup_paths for p in paths):
                    continue
                # Check duration similarity
                durations = [t[1] for t in track_tuples if t[1] is not None]
                if not durations or (max(durations) - min(durations) <= 4.0):
                    info = self.pipeline.extract_file_info(paths[0])
                    report.duplicates.append(
                        DuplicateGroup(
                            artist=info.get("artist") or n_art,
                            title=info.get("title") or n_tit,
                            tracks=paths,
                            match_type="fuzzy_tag",
                        )
                    )

        # Incomplete Albums calculation
        report.total_albums = len(albums_map)
        for alb_key, data in albums_map.items():
            discs = data["discs"]
            max_disc = max(discs.keys(), default=1)
            disc_total = max(data["disc_totals"], default=None)
            total_discs = max(disc_total or 1, max_disc)
            is_multi_disc = total_discs > 1 or len(discs) > 1

            if is_multi_disc:
                missing_items = []
                present_items = []
                all_discs = range(1, total_discs + 1)
                total_expected_tracks = 0

                for d in all_discs:
                    if d not in discs:
                        missing_items.append(f"Disc {d} (Entire disc)")
                        continue

                    d_info = discs[d]
                    pres = sorted(list(d_info["present_tracks"]))
                    d_tt = max(d_info["track_totals"], default=None)
                    global_tt = max(data["track_totals"], default=None)

                    # If track_total is global across all discs (e.g. 24 for 3 discs), don't expect 24 on a single disc
                    if d_tt and d_tt > len(pres) and global_tt and global_tt == d_tt and global_tt > len(pres):
                        expected_count = max(pres, default=0)
                    elif d_tt:
                        expected_count = d_tt
                    else:
                        expected_count = max(pres, default=0)

                    total_expected_tracks += expected_count
                    expected_set = set(range(1, expected_count + 1))
                    miss = sorted(list(expected_set - set(pres)))
                    if miss:
                        miss_formatted = ", ".join(str(m) for m in miss)
                        missing_items.append(f"Disc {d}: [{miss_formatted}]")

                    if len(pres) > 1:
                        present_items.append(f"Disc {d} ({len(pres)} tracks: {pres[0]}-{pres[-1]})")
                    elif pres:
                        present_items.append(f"Disc {d} (Track {pres[0]})")
                    else:
                        present_items.append(f"Disc {d} (0 tracks)")

                global_tt = max(data["track_totals"], default=None)
                if global_tt and not missing_items and data["total_files"] < global_tt:
                    missing_items.append(f"{global_tt - data['total_files']} tracks missing")

                if missing_items:
                    folder = next(iter(data["folders"])) if data["folders"] else target_dir
                    display_total = global_tt or total_expected_tracks
                    report.incomplete_albums.append(
                        IncompleteAlbum(
                            album_artist=data["album_artist"],
                            album_title=data["album_title"],
                            track_total=display_total,
                            present_tracks=present_items,
                            missing_tracks=missing_items,
                            folder=folder,
                        )
                    )
            else:
                d_info = discs.get(1, {"present_tracks": set(), "track_totals": set()})
                pres = sorted(list(d_info["present_tracks"]))
                tt = max(data["track_totals"], default=None) or (max(pres) if pres else 0)
                if tt and tt > 1:
                    expected = set(range(1, tt + 1))
                    missing = sorted(list(expected - set(pres)))
                    if missing:
                        folder = next(iter(data["folders"])) if data["folders"] else target_dir
                        report.incomplete_albums.append(
                            IncompleteAlbum(
                                album_artist=data["album_artist"],
                                album_title=data["album_title"],
                                track_total=tt,
                                present_tracks=pres,
                                missing_tracks=missing,
                                folder=folder,
                            )
                        )

        # 7. Fragmented Collaborative Folders audit
        try:
            from apolo.utils import parse_artists
            root_dirs = [p for p in target_dir.iterdir() if p.is_dir() and "Playlists" not in p.parts and p.name.lower() != "various artists"]
            for folder in root_dirs:
                m_artists, _, all_a, _ = parse_artists(folder.name)
                if len(all_a) > 1 and m_artists:
                    primary_name = m_artists[0]
                    base_dir = self.pipeline.organizer._resolve_case_insensitive_dir(target_dir, primary_name)
                    if base_dir.exists() and base_dir.resolve() != folder.resolve():
                        report.fragmented_artist_folders.append((folder, base_dir, primary_name))
        except Exception:
            pass

        # Calculate Health Score (excluding lyrics, as lyrics depend on external API availability)
        score = 100.0
        lyrics_cov = 100.0
        if report.total_tracks > 0:
            dup_pen = min(30.0, (len(report.duplicates) * 3.0))
            inc_pen = min(30.0, (len(report.incomplete_albums) * 10.0))
            cov_pen = min(25.0, (len(report.missing_or_lowres_covers) / report.total_tracks) * 25.0)
            tag_pen = min(25.0, (len(report.missing_essential_tags) / report.total_tracks) * 25.0)
            frag_pen = min(15.0, (len(report.fragmented_artist_folders) * 5.0))
            score = max(0.0, 100.0 - (dup_pen + inc_pen + cov_pen + tag_pen + frag_pen))

            tracks_with_lyrics = max(0, report.total_tracks - len(report.missing_lyrics))
            lyrics_cov = (tracks_with_lyrics / report.total_tracks) * 100.0

        report.health_score = round(score, 1)
        report.lyrics_coverage = round(lyrics_cov, 1)
        return report

    def repair_fragmented_folders(
        self,
        fragmented: List[Tuple[Path, Path, str]],
        on_progress: Optional[Callable[[str, str], None]] = None,
    ) -> int:
        """Unifies fragmented collaborative artist folders into their primary artist folder."""
        repaired = 0
        for folder, base_dir, primary_name in fragmented:
            if not folder.exists():
                continue
            audio_files = [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS]
            if not audio_files:
                try:
                    folder.rmdir()
                except Exception:
                    pass
                continue

            for idx, af in enumerate(audio_files, 1):
                if on_progress:
                    on_progress("fragmented", f"Unifying ({idx}/{len(audio_files)}): {af.name} -> {primary_name}")
                AudioTagger.update_tags(af, {"album_artist": primary_name})

            self.pipeline.reorganize_paths(audio_files)
            repaired += 1

            # Remove empty directory
            try:
                for sub in sorted(folder.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                    if sub.is_dir() and not any(sub.iterdir()):
                        sub.rmdir()
                if folder.exists() and not any(folder.iterdir()):
                    folder.rmdir()
            except Exception:
                pass

        return repaired

    def repair_lyrics(
        self,
        tracks: List[Path],
        on_progress: Optional[Callable[[str, str], None]] = None,
    ) -> int:
        """Fetches and embeds missing synced lyrics for given tracks from LRCLIB."""
        repaired = 0
        for idx, file_path in enumerate(tracks, 1):
            if not file_path.exists():
                continue
            info = self.pipeline.extract_file_info(file_path)
            title = info.get("title") or file_path.stem
            artist = info.get("artist") or "Unknown Artist"
            album = info.get("album")
            duration = info.get("duration")

            if on_progress:
                on_progress("lyrics", f"Fetching lyrics for ({idx}/{len(tracks)}): {artist} - {title}")

            synced = self.lyrics_provider.get_synced_lyrics(
                track_name=title,
                artist_name=artist,
                album_name=album,
                duration=duration,
            )
            if synced:
                AudioTagger.update_tags(file_path, {"lyrics": synced})
                if self.config.organization.save_lrc_file:
                    lrc_path = file_path.with_suffix(".lrc")
                    lrc_path.write_text(synced, encoding="utf-8")
                repaired += 1

        return repaired

    def repair_covers(
        self,
        tracks: List[Path],
        on_progress: Optional[Callable[[str, str], None]] = None,
    ) -> int:
        """Re-queries providers to fetch and embed high-resolution covers for tracks."""
        repaired = 0
        for idx, file_path in enumerate(tracks, 1):
            if not file_path.exists():
                continue
            info = self.pipeline.extract_file_info(file_path)
            title = info.get("title") or file_path.stem
            artist = info.get("artist") or "Unknown Artist"

            if on_progress:
                on_progress("cover", f"Searching cover for ({idx}/{len(tracks)}): {artist} - {title}")

            query = f"{artist} {title}"
            match = self.matcher.find_best_match(
                query=query,
                expected_title=title,
                expected_artist=artist,
                expected_album=info.get("album"),
                expected_duration=info.get("duration"),
            )
            if match and match.cover_art_data:
                AudioTagger.update_tags(file_path, {}, cover_data=match.cover_art_data)
                repaired += 1

        return repaired
