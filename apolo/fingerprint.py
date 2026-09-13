import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests

from apolo.config import ApoloConfig, load_config
from apolo.metadata.models import TrackMetadata

ACOUSTID_API_URL = "https://api.acoustid.org/v2/lookup"
DEFAULT_ACOUSTID_CLIENT_KEY = "8XaBELgH"  # Standard public application key for AcoustID queries


class AcousticFingerprinter:
    """
    Computes Chromaprint acoustic fingerprints using 'fpcalc' and queries AcoustID
    to identify untagged audio tracks by their actual audio waveform.
    """

    def __init__(self, config: Optional[ApoloConfig] = None, api_key: Optional[str] = None):
        self.config = config or load_config()
        self.api_key = api_key or os.environ.get("ACOUSTID_API_KEY", DEFAULT_ACOUSTID_CLIENT_KEY)

    @staticmethod
    def is_fpcalc_available() -> bool:
        """Returns True if the 'fpcalc' command-line binary is installed and executable."""
        return shutil.which("fpcalc") is not None

    def fingerprint_file(self, file_path: Path) -> Tuple[Optional[float], Optional[str]]:
        """
        Calculates the audio duration and Chromaprint fingerprint string for a local audio file.
        Returns: (duration_in_seconds, fingerprint_string) or (None, None) on failure.
        """
        if not file_path.exists():
            return None, None

        if not self.is_fpcalc_available():
            # Fallback: cannot calculate acoustic fingerprint without fpcalc
            return None, None

        try:
            cmd = ["fpcalc", "-json", str(file_path)]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if proc.returncode != 0:
                return None, None

            data = json.loads(proc.stdout)
            duration = float(data.get("duration", 0.0))
            fingerprint = data.get("fingerprint")
            return duration, fingerprint
        except Exception:
            return None, None

    def lookup_fingerprint(self, duration: float, fingerprint: str) -> List[TrackMetadata]:
        """
        Queries AcoustID API with duration and fingerprint, parsing matched recordings
        and release groups into structured TrackMetadata objects.
        """
        if not fingerprint or duration <= 0:
            return []

        params = {
            "client": self.api_key,
            "meta": "recordings releasegroups releases tracks compress",
            "duration": str(int(duration)),
            "fingerprint": fingerprint,
        }

        try:
            resp = requests.get(ACOUSTID_API_URL, params=params, timeout=12)
            if resp.status_code != 200:
                return []

            data = resp.json()
            if data.get("status") != "ok":
                return []

            results: List[TrackMetadata] = []
            seen_recordings = set()

            for res in data.get("results", []):
                for rec in res.get("recordings", []):
                    rec_id = rec.get("id")
                    if rec_id in seen_recordings:
                        continue
                    seen_recordings.add(rec_id)

                    title = rec.get("title")
                    if not title:
                        continue

                    # Extract artist name(s)
                    artist_names = []
                    for artist_obj in rec.get("artists", []):
                        if isinstance(artist_obj, dict) and "name" in artist_obj:
                            artist_names.append(artist_obj["name"])
                        elif isinstance(artist_obj, str):
                            artist_names.append(artist_obj)
                    artist = ", ".join(artist_names) if artist_names else "Unknown Artist"

                    # Extract album, date, track number if available in releasegroups / releases
                    album = None
                    album_artist = None
                    release_date = None
                    track_number = None
                    track_total = None
                    disc_number = None
                    disc_total = None

                    release_groups = rec.get("releasegroups", [])
                    if release_groups:
                        rg = release_groups[0]
                        album = rg.get("title")
                        rg_artists = [a.get("name") for a in rg.get("artists", []) if isinstance(a, dict) and "name" in a]
                        if rg_artists:
                            album_artist = ", ".join(rg_artists)
                        if "releases" in rg and rg["releases"]:
                            rel = rg["releases"][0]
                            if "date" in rel:
                                release_date = str(rel["date"].get("year", "")) if isinstance(rel["date"], dict) else str(rel.get("date", ""))
                            if "mediums" in rel and rel["mediums"]:
                                med = rel["mediums"][0]
                                disc_number = med.get("position")
                                disc_total = rel.get("medium_count")
                                if "tracks" in med and med["tracks"]:
                                    trk = med["tracks"][0]
                                    track_number = trk.get("position")
                                    track_total = med.get("track_count")

                    meta = TrackMetadata(
                        title=title,
                        artist=artist,
                        album_artist=album_artist or artist,
                        album=album or "Single",
                        track_number=track_number,
                        track_total=track_total,
                        disc_number=disc_number,
                        disc_total=disc_total,
                        date=release_date,
                        duration=rec.get("duration") or duration,
                        provider_source="acoustid",
                        source_id=rec_id,
                    )
                    results.append(meta)

            return results
        except Exception:
            return []

    def identify_file(self, file_path: Path) -> Optional[TrackMetadata]:
        """
        End-to-end identification: generates acoustic fingerprint and queries AcoustID.
        Returns top matched TrackMetadata if found.
        """
        duration, fingerprint = self.fingerprint_file(file_path)
        if not duration or not fingerprint:
            return None

        candidates = self.lookup_fingerprint(duration, fingerprint)
        if candidates:
            return candidates[0]
        return None
