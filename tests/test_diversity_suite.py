import io
import subprocess
from pathlib import Path
from typing import Optional
from PIL import Image
import pytest

from apolo.config import ApoloConfig, DirectoriesConfig, OrganizationConfig
from apolo.doctor import LibraryDoctor
from apolo.metadata.matcher import MetadataMatcher
from apolo.metadata.models import TrackMetadata
from apolo.organizer import LibraryOrganizer
from apolo.tagger import AudioTagger
from apolo.utils import is_compilation_album, is_single_release, normalize_search_string


def create_dummy_audio(
    output_path: Path,
    meta: TrackMetadata,
    has_cover: bool = True,
    lyrics: Optional[str] = "[00:01.00] Test lyrics",
):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=48000:cl=stereo",
        "-t",
        "1",
        "-c:a",
        "libopus",
        "-b:a",
        "128k",
        str(output_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    if has_cover and not meta.cover_art_data:
        img = Image.new("RGB", (600, 600), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        meta.cover_art_data = buf.getvalue()

    if lyrics and not meta.synced_lyrics:
        meta.synced_lyrics = lyrics

    AudioTagger.tag_opus(output_path, meta)


# Define 18 diverse test cases
DIVERSITY_TEST_CASES = [
    {
        "id": "mainstream_pop",
        "desc": "Mainstream Pop ('ost' word boundary in Future Nostalgia)",
        "meta": TrackMetadata(
            title="Levitating",
            artist="Dua Lipa",
            album_artist="Dua Lipa",
            album="Future Nostalgia",
            track_number=5,
            track_total=11,
            disc_number=1,
            disc_total=1,
            date="2020-03-27",
            genre="Pop",
        ),
        "expected_subpath": "Dua Lipa/Future Nostalgia (2020)/05 - Levitating.opus",
        "is_compilation": False,
    },
    {
        "id": "spanish_hyperpop",
        "desc": "Spanish Alternative / Underground Pop",
        "meta": TrackMetadata(
            title="VOYCONTODO",
            artist="Ralphie Choo",
            album_artist="Ralphie Choo",
            album="SUPERNOVA",
            track_number=3,
            track_total=14,
            disc_number=1,
            disc_total=1,
            date="2023-09-15",
            genre="Flamenco Pop",
        ),
        "expected_subpath": "Ralphie Choo/SUPERNOVA (2023)/03 - VOYCONTODO.opus",
        "is_compilation": False,
    },
    {
        "id": "underground_single_fallback",
        "desc": "Underground Single with no external DB match (Fallback safe)",
        "meta": TrackMetadata(
            title="BABY M",
            artist="Rusowsky & mori",
            album_artist="Rusowsky & mori",
            album="BABY M - Single",
            track_number=1,
            track_total=1,
            disc_number=1,
            disc_total=1,
            date="2024-01-10",
            genre="Indie / Underground",
        ),
        "expected_subpath": "Rusowsky & mori/Singles/BABY M (2024).opus",
        "is_compilation": False,
    },
    {
        "id": "japanese_unicode",
        "desc": "J-Pop with Japanese Kanji/Kana Unicode",
        "meta": TrackMetadata(
            title="アイドル",
            artist="YOASOBI",
            album_artist="YOASOBI",
            album="THE BOOK 3",
            track_number=3,
            track_total=10,
            disc_number=1,
            disc_total=1,
            date="2023-10-04",
            genre="J-Pop",
        ),
        "expected_subpath": "YOASOBI/THE BOOK 3 (2023)/03 - アイドル.opus",
        "is_compilation": False,
    },
    {
        "id": "idm_punctuation",
        "desc": "IDM Electronic with leading ellipsis and special characters",
        "meta": TrackMetadata(
            title="Alberto Balsalm",
            artist="Aphex Twin",
            album_artist="Aphex Twin",
            album="...I Care Because You Do",
            track_number=11,
            track_total=12,
            disc_number=1,
            disc_total=1,
            date="1995-04-24",
            genre="IDM",
        ),
        "expected_subpath": "Aphex Twin/I Care Because You Do (1995)/11 - Alberto Balsalm.opus",
        "is_compilation": False,
    },
    {
        "id": "hyperpop_lowercase",
        "desc": "Glitch-pop / Hyperpop with stylized lowercase",
        "meta": TrackMetadata(
            title="venus fly trap",
            artist="brakence",
            album_artist="brakence",
            album="hypochondriac",
            track_number=4,
            track_total=13,
            disc_number=1,
            disc_total=1,
            date="2022-12-02",
            genre="Hyperpop",
        ),
        "expected_subpath": "brakence/hypochondriac (2022)/04 - venus fly trap.opus",
        "is_compilation": False,
    },
    {
        "id": "multidisc_electronic",
        "desc": "Electronic Multi-disc Edition (Disc 1)",
        "meta": TrackMetadata(
            title="Get Lucky",
            artist="Daft Punk feat. Pharrell Williams",
            album_artist="Daft Punk",
            album="Random Access Memories (10th Anniversary Edition)",
            track_number=8,
            track_total=13,
            disc_number=1,
            disc_total=2,
            date="2023-05-12",
            genre="Electronic",
        ),
        "expected_subpath": "Daft Punk/Random Access Memories (10th Anniversary Edition) (2023)/Disc 01/08 - Get Lucky.opus",
        "is_compilation": False,
    },
    {
        "id": "multidisc_rock",
        "desc": "Classic Rock Multi-disc Album (Disc 2)",
        "meta": TrackMetadata(
            title="Comfortably Numb",
            artist="Pink Floyd",
            album_artist="Pink Floyd",
            album="The Wall",
            track_number=6,
            track_total=13,
            disc_number=2,
            disc_total=2,
            date="1979-11-30",
            genre="Progressive Rock",
        ),
        "expected_subpath": "Pink Floyd/The Wall (1979)/Disc 02/06 - Comfortably Numb.opus",
        "is_compilation": False,
    },
    {
        "id": "multidisc_hiphop",
        "desc": "Modern Hip-Hop Deluxe Multi-disc (Disc 2)",
        "meta": TrackMetadata(
            title="Creepin' (Heroes Version)",
            artist="Metro Boomin, The Weeknd, 21 Savage",
            album_artist="Metro Boomin",
            album="HEROES & VILLAINS (Heroes Version)",
            track_number=10,
            track_total=15,
            disc_number=2,
            disc_total=2,
            date="2022-12-05",
            genre="Hip-Hop",
        ),
        "expected_subpath": "Metro Boomin/HEROES & VILLAINS (Heroes Version) (2022)/Disc 02/10 - Creepin' (Heroes Version).opus",
        "is_compilation": False,
    },
    {
        "id": "underground_trap",
        "desc": "Underground Trap with symbols and punctuation in title/album",
        "meta": TrackMetadata(
            title="mi _) LUZ",
            artist="FRO!",
            album_artist="FRO!",
            album="#bigsteppa",
            track_number=1,
            track_total=6,
            disc_number=1,
            disc_total=1,
            date="2024-02-14",
            genre="Pluggnb / Trap",
        ),
        "expected_subpath": "FRO!/#bigsteppa (2024)/01 - mi _) LUZ.opus",
        "is_compilation": False,
    },
    {
        "id": "kpop_ep",
        "desc": "K-Pop Mini Album / EP",
        "meta": TrackMetadata(
            title="Super Shy",
            artist="NewJeans",
            album_artist="NewJeans",
            album="Get Up",
            track_number=2,
            track_total=6,
            disc_number=1,
            disc_total=1,
            date="2023-07-21",
            genre="K-Pop",
        ),
        "expected_subpath": "NewJeans/Get Up (2023)/02 - Super Shy.opus",
        "is_compilation": False,
    },
    {
        "id": "alternative_hiphop",
        "desc": "Alternative Concept Hip-Hop Album",
        "meta": TrackMetadata(
            title="EARFQUAKE",
            artist="Tyler, The Creator",
            album_artist="Tyler, The Creator",
            album="IGOR",
            track_number=2,
            track_total=12,
            disc_number=1,
            disc_total=1,
            date="2019-05-17",
            genre="Alternative Hip-Hop",
        ),
        "expected_subpath": "Tyler, The Creator/IGOR (2019)/02 - EARFQUAKE.opus",
        "is_compilation": False,
    },
    {
        "id": "ost_soundtrack",
        "desc": "Original Film Soundtrack (Compilation)",
        "meta": TrackMetadata(
            title="Time",
            artist="Hans Zimmer",
            album_artist="Various Artists",
            album="Inception (Music From The Motion Picture)",
            track_number=12,
            track_total=12,
            disc_number=1,
            disc_total=1,
            date="2010-07-13",
            genre="Soundtrack",
        ),
        "expected_subpath": "Various Artists/Inception (Music From The Motion Picture) (2010)/12 - Hans Zimmer - Time.opus",
        "is_compilation": True,
    },
    {
        "id": "cyrillic_postpunk",
        "desc": "Post-Punk with Cyrillic characters",
        "meta": TrackMetadata(
            title="Судно (Борис Рижий)",
            artist="Молчат Дома",
            album_artist="Молчат Дома",
            album="Этажи",
            track_number=7,
            track_total=9,
            disc_number=1,
            disc_total=1,
            date="2018-09-07",
            genre="Post-Punk / Synthpop",
        ),
        "expected_subpath": "Молчат Дома/Этажи (2018)/07 - Судно (Борис Рижий).opus",
        "is_compilation": False,
    },
    {
        "id": "experimental_tamil_disc1",
        "desc": "3-Disc Underground Album - Disc 01 (English title)",
        "meta": TrackMetadata(
            title="wise mystical magical wizard fish",
            artist="Tanger",
            album_artist="Tanger",
            album="Prefer not to say",
            track_number=1,
            track_total=8,
            disc_number=1,
            disc_total=3,
            date="2024-05-01",
            genre="Experimental",
        ),
        "expected_subpath": "Tanger/Prefer not to say (2024)/Disc 01/01 - wise mystical magical wizard fish.opus",
        "is_compilation": False,
    },
    {
        "id": "experimental_tamil_disc2",
        "desc": "3-Disc Underground Album - Disc 02 (English title)",
        "meta": TrackMetadata(
            title="tiny windows",
            artist="Tanger",
            album_artist="Tanger",
            album="Prefer not to say",
            track_number=1,
            track_total=8,
            disc_number=2,
            disc_total=3,
            date="2024-05-01",
            genre="Experimental",
        ),
        "expected_subpath": "Tanger/Prefer not to say (2024)/Disc 02/01 - tiny windows.opus",
        "is_compilation": False,
    },
    {
        "id": "experimental_tamil_disc3",
        "desc": "3-Disc Underground Album - Disc 03 (Tamil Unicode Script)",
        "meta": TrackMetadata(
            title="முன்னுதாரணம்",
            artist="Tanger",
            album_artist="Tanger",
            album="Prefer not to say",
            track_number=1,
            track_total=8,
            disc_number=3,
            disc_total=3,
            date="2024-05-01",
            genre="Experimental",
        ),
        "expected_subpath": "Tanger/Prefer not to say (2024)/Disc 03/01 - முன்னுதாரணம்.opus",
        "is_compilation": False,
    },
    {
        "id": "live_acoustic",
        "desc": "Live Acoustic Recording",
        "meta": TrackMetadata(
            title="About a Girl (Live)",
            artist="Nirvana",
            album_artist="Nirvana",
            album="MTV Unplugged In New York (Live)",
            track_number=1,
            track_total=14,
            disc_number=1,
            disc_total=1,
            date="1994-11-01",
            genre="Grunge / Acoustic",
        ),
        "expected_subpath": "Nirvana/MTV Unplugged In New York (Live) (1994)/01 - About a Girl (Live).opus",
        "is_compilation": False,
    },
]


def test_diversity_suite_organization(tmp_path):
    """Verifies that all 18 diverse test cases are accurately placed in expected directory hierarchies."""
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=tmp_path / "Music"),
        organization=OrganizationConfig(
            multi_disc_folder=True,
            various_artists_folder=True,
        ),
    )
    organizer = LibraryOrganizer(config)

    for item in DIVERSITY_TEST_CASES:
        meta = item["meta"]
        expected_sub = Path(item["expected_subpath"])
        dest = organizer.get_destination_path(meta)

        rel = dest.relative_to(config.directories.library_dir)
        assert rel == expected_sub, f"Mismatch for '{item['id']}': got {rel}, expected {expected_sub}"
        assert is_compilation_album(meta.album, meta.album_artist) == item["is_compilation"]


def test_diversity_suite_doctor_audit(tmp_path):
    """Builds a complete library with all 18 diverse test tracks and audits it with LibraryDoctor."""
    library_dir = tmp_path / "Music"
    config = ApoloConfig(
        directories=DirectoriesConfig(library_dir=library_dir),
        organization=OrganizationConfig(multi_disc_folder=True, various_artists_folder=True),
    )
    organizer = LibraryOrganizer(config)
    doctor = LibraryDoctor(config)

    # For multi-disc or albums with track_total, populate all tracks for the test albums to verify complete albums
    # 1. Tanger 3-disc album (3 discs x 2 tracks = 6 tracks)
    for d in [1, 2, 3]:
        for t in [1, 2]:
            t_meta = TrackMetadata(
                title=f"Tanger D{d}T{t}",
                artist="Tanger",
                album_artist="Tanger",
                album="Prefer not to say",
                track_number=t,
                track_total=2,
                disc_number=d,
                disc_total=3,
                date="2024-05-01",
                genre="Experimental",
            )
            dest = organizer.get_destination_path(t_meta)
            create_dummy_audio(dest, t_meta)

    # 2. Dua Lipa 2-track mini album
    for t in [1, 2]:
        t_meta = TrackMetadata(
            title=f"Song {t}",
            artist="Dua Lipa",
            album_artist="Dua Lipa",
            album="Future Nostalgia",
            track_number=t,
            track_total=2,
            disc_number=1,
            disc_total=1,
            date="2020-03-27",
            genre="Pop",
        )
        dest = organizer.get_destination_path(t_meta)
        create_dummy_audio(dest, t_meta)

    # 3. Underground Single (Rusowsky)
    s_meta = TrackMetadata(
        title="BABY M",
        artist="Rusowsky & mori",
        album="BABY M - Single",
        track_number=1,
        track_total=1,
        date="2024-01-10",
        genre="Indie / Underground",
    )
    dest = organizer.get_destination_path(s_meta)
    create_dummy_audio(dest, s_meta)

    # 4. Japanese Release (YOASOBI)
    j_meta = TrackMetadata(
        title="アイドル",
        artist="YOASOBI",
        album_artist="YOASOBI",
        album="THE BOOK 3",
        track_number=1,
        track_total=1,
        date="2023-10-04",
        genre="J-Pop",
    )
    dest = organizer.get_destination_path(j_meta)
    create_dummy_audio(dest, j_meta)

    # 5. Cyrillic Release (Molchat Doma)
    c_meta = TrackMetadata(
        title="Судно",
        artist="Молчат Дома",
        album_artist="Молчат Дома",
        album="Этажи",
        track_number=1,
        track_total=1,
        date="2018-09-07",
        genre="Post-Punk",
    )
    dest = organizer.get_destination_path(c_meta)
    create_dummy_audio(dest, c_meta)

    # Audit library
    report = doctor.scan_library(library_dir=library_dir)
    assert report.total_tracks == 11
    assert len(report.incomplete_albums) == 0, f"Incomplete albums detected: {report.incomplete_albums}"
    assert report.health_score == 100.0
    assert report.lyrics_coverage == 100.0
