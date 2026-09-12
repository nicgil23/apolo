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

    def search_all(self, query: str, limit_per_provider: int = 5) -> List[TrackMetadata]:
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

    def find_best_match(
        self,
        query: str,
        expected_title: Optional[str] = None,
        expected_artist: Optional[str] = None,
        expected_duration: Optional[float] = None,
    ) -> Optional[TrackMetadata]:
        # Formulate search queries
        clean_title = normalize_search_string(expected_title or query)
        clean_artist = normalize_search_string(expected_artist or "")
        primary_artist = normalize_search_string(extract_primary_artist(expected_artist) or "")

        queries = []
        if clean_artist and clean_title:
            queries.append(f"{clean_artist} {clean_title}")
            if primary_artist and primary_artist != clean_artist:
                queries.append(f"{primary_artist} {clean_title}")
        elif query:
            queries.append(normalize_search_string(query))

        if clean_title and clean_title not in queries:
            queries.append(clean_title)

        candidates: List[TrackMetadata] = []
        for q in queries:
            if not q.strip():
                continue
            candidates.extend(self.search_all(q))
            # If we already have candidates from specific queries, we can stop searching more generic ones
            if len(candidates) >= 5:
                break

        if not candidates:
            return None

        # Score and filter candidates strictly
        scored_candidates: List[tuple[float, TrackMetadata]] = []
        for cand in candidates:
            score = self._compute_similarity_score(
                cand, clean_title, clean_artist, primary_artist, expected_duration
            )
            if score >= 65.0:
                scored_candidates.append((score, cand))

        if not scored_candidates:
            return None

        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        best_meta = scored_candidates[0][1]

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
        expected_duration: Optional[float],
    ) -> float:
        cand_title = normalize_search_string(meta.title)
        cand_artist = normalize_search_string(meta.artist)

        # 1. Title Similarity Check (MANDATORY)
        if clean_title:
            title_ratio = fuzz.ratio(clean_title.lower(), cand_title.lower())
            title_partial = fuzz.partial_ratio(clean_title.lower(), cand_title.lower())
            best_title_score = max(title_ratio, title_partial)

            # If title does not match well, reject completely to avoid false positive matches
            if title_ratio < 50 and title_partial < 75:
                return 0.0
        else:
            best_title_score = 70.0

        # 2. Artist Similarity Check
        if clean_artist or primary_artist:
            artist_scores = []
            if clean_artist:
                artist_scores.append(fuzz.token_set_ratio(clean_artist.lower(), cand_artist.lower()))
                artist_scores.append(fuzz.ratio(clean_artist.lower(), cand_artist.lower()))
            if primary_artist:
                artist_scores.append(fuzz.token_set_ratio(primary_artist.lower(), cand_artist.lower()))
                artist_scores.append(fuzz.ratio(primary_artist.lower(), cand_artist.lower()))

            best_artist_score = max(artist_scores) if artist_scores else 0.0

            # If we know the artist and the candidate artist has almost zero correlation, reject
            if best_artist_score < 40:
                return 0.0
        else:
            best_artist_score = 70.0

        score = (best_title_score * 0.6) + (best_artist_score * 0.4)

        # 3. Duration Bonus/Penalty
        if expected_duration and meta.duration:
            delta = abs(expected_duration - meta.duration)
            if delta <= 4:
                score += 5.0
            elif delta > 25:
                score -= min(25.0, (delta - 25) * 0.5)

        return max(0.0, score)

    def _download_cover(self, url: str) -> Optional[bytes]:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.content
        except Exception:
            pass
        return None
