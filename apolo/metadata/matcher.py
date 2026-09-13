from typing import List, Optional, Set
import requests
from rapidfuzz import fuzz

from apolo.config import ApoloConfig, load_config
from apolo.metadata.deezer import DeezerProvider
from apolo.metadata.itunes import iTunesProvider
from apolo.metadata.models import TrackMetadata
from apolo.metadata.musicbrainz import MusicBrainzProvider
from apolo.utils import extract_primary_artist, normalize_search_string


class MetadataMatcher:
    def __init__(self, config: Optional[ApoloConfig] = None):
        self.config = config or load_config()
        self.itunes = iTunesProvider()
        self.deezer = DeezerProvider()
        self.musicbrainz = MusicBrainzProvider()

    def search_all(self, query: str, limit_per_provider: int = 10) -> List[TrackMetadata]:
        results: List[TrackMetadata] = []
        seen_ids: Set[str] = set()

        def add_unique(items: List[TrackMetadata]):
            for item in items:
                uid = f"{item.provider_source}:{item.source_id or (item.artist + item.title)}"
                if uid not in seen_ids:
                    seen_ids.add(uid)
                    results.append(item)

        if self.config.providers.prefer_deezer:
            add_unique(self.deezer.search(query, limit=limit_per_provider))

        if self.config.providers.prefer_itunes:
            add_unique(self.itunes.search(query, limit=limit_per_provider))

        if self.config.providers.prefer_musicbrainz and not results:
            add_unique(self.musicbrainz.search(query, limit=limit_per_provider))

        return results

    def get_ranked_candidates(
        self,
        query: str,
        expected_title: Optional[str] = None,
        expected_artist: Optional[str] = None,
        expected_album: Optional[str] = None,
        expected_duration: Optional[float] = None,
        min_score: float = 40.0,
    ) -> List[tuple[float, TrackMetadata]]:
        clean_title = normalize_search_string(expected_title or query)
        raw_artist = expected_artist or ""
        primary_artist = extract_primary_artist(raw_artist) or raw_artist
        clean_primary = normalize_search_string(primary_artist)
        clean_artist = normalize_search_string(raw_artist)
        clean_album = normalize_search_string(expected_album or "")

        queries: List[str] = []
        # 1. Primary artist + Album + Title (Highest priority when album context is known)
        if clean_primary and clean_album and clean_title and clean_album.lower() not in ["single", "unknown"]:
            queries.append(f"{clean_primary} {clean_album} {clean_title}")
        # 2. Primary artist + Title (Multi-artist collaborations)
        if clean_primary and clean_title:
            queries.append(f"{clean_primary} {clean_title}")
        # 3. Primary artist + Album
        if clean_primary and clean_album and clean_album.lower() not in ["single", "unknown"]:
            queries.append(f"{clean_primary} {clean_album}")
        # 4. Full artist string + Title
        if clean_artist and clean_title and clean_artist != clean_primary:
            queries.append(f"{clean_artist} {clean_title}")
        # 5. Standalone Title
        if clean_title and clean_title not in queries:
            queries.append(clean_title)

        candidates: List[TrackMetadata] = []
        for q in queries:
            if not q.strip():
                continue
            found = self.search_all(q)
            candidates.extend(found)
            if len(candidates) >= 20:
                break

        if not candidates:
            return []

        # Score candidates strictly
        scored_candidates: List[tuple[float, TrackMetadata]] = []
        for cand in candidates:
            score = self._compute_similarity_score(
                cand, clean_title, clean_artist, clean_primary, clean_album, expected_duration
            )
            if score >= min_score:
                scored_candidates.append((score, cand))

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        return scored_candidates

    def find_best_match(
        self,
        query: str,
        expected_title: Optional[str] = None,
        expected_artist: Optional[str] = None,
        expected_album: Optional[str] = None,
        expected_duration: Optional[float] = None,
    ) -> Optional[TrackMetadata]:
        ranked = self.get_ranked_candidates(
            query=query,
            expected_title=expected_title,
            expected_artist=expected_artist,
            expected_album=expected_album,
            expected_duration=expected_duration,
            min_score=70.0,
        )
        if not ranked:
            return None

        best_meta = ranked[0][1]

        # Download cover art if available
        if self.config.organization.embed_cover_art and best_meta.cover_art_url:
            best_meta.cover_art_data = self._download_cover(best_meta.cover_art_url)

        return best_meta

    def _compute_similarity_score(
        self,
        meta: TrackMetadata,
        clean_title: str,
        clean_artist: str,
        primary_artist: str,
        clean_album: str,
        expected_duration: Optional[float],
    ) -> float:
        cand_title = normalize_search_string(meta.title)
        cand_artist = normalize_search_string(meta.artist)
        cand_album = normalize_search_string(meta.album or "")

        # 1. Title Similarity Check (MANDATORY)
        if clean_title:
            title_ratio = fuzz.ratio(clean_title.lower(), cand_title.lower())
            title_partial = fuzz.partial_ratio(clean_title.lower(), cand_title.lower())
            title_token = fuzz.token_sort_ratio(clean_title.lower(), cand_title.lower())
            best_title_score = max(title_ratio, title_partial, title_token)

            if title_ratio < 45 and title_partial < 70 and title_token < 60:
                return 0.0
        else:
            best_title_score = 70.0

        # 2. Artist Similarity Check
        if clean_artist or primary_artist:
            artist_scores = []
            if primary_artist:
                artist_scores.append(fuzz.ratio(primary_artist.lower(), cand_artist.lower()))
                artist_scores.append(fuzz.token_set_ratio(primary_artist.lower(), cand_artist.lower()))
            if clean_artist:
                artist_scores.append(fuzz.ratio(clean_artist.lower(), cand_artist.lower()))
                artist_scores.append(fuzz.token_set_ratio(clean_artist.lower(), cand_artist.lower()))

            best_artist_score = max(artist_scores) if artist_scores else 0.0

            # If we know the artist and candidate has no correlation, reject
            if best_artist_score < 50:
                return 0.0

            # For short titles, require high title ratio unless artist is exact match
            if len(clean_title) <= 6 and best_artist_score < 80 and title_ratio < 75:
                return 0.0
        else:
            best_artist_score = 70.0

        score = (best_title_score * 0.55) + (best_artist_score * 0.45)

        # 3. Album Similarity Check & Bonus/Penalty
        if clean_album and clean_album.lower() not in ["single", "unknown"]:
            if cand_album:
                alb_ratio = fuzz.ratio(clean_album.lower(), cand_album.lower())
                alb_token = fuzz.token_set_ratio(clean_album.lower(), cand_album.lower())
                best_alb_score = max(alb_ratio, alb_token)
                if best_alb_score >= 75:
                    score += 25.0
                elif best_alb_score < 40:
                    score -= 20.0
            else:
                score -= 10.0

        # 4. Duration Bonus/Penalty
        if expected_duration and meta.duration:
            delta = abs(expected_duration - meta.duration)
            if delta <= 4:
                score += 5.0
            elif delta > 25:
                score -= min(25.0, (delta - 25) * 0.5)

        # 5. Metadata Completeness Bonus (disc total, track total, date)
        if meta.track_number is not None:
            score += 1.0
        if meta.track_total is not None:
            score += 1.0
        if meta.disc_total is not None and meta.disc_total > 1:
            score += 2.0
        if meta.date:
            score += 0.5

        return max(0.0, score)

    def _download_cover(self, url: str) -> Optional[bytes]:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.content
        except Exception:
            pass
        return None
