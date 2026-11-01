#!/usr/bin/env python3
import os
import sys
import argparse
from collections import defaultdict, Counter
import mutagen
from apolo.metadata.matcher import MetadataMatcher

GENRE_MAPPING = {
    # Trap & Hip-Hop / Rap
    "Trap / Hip-Hop": "Trap",
    "Trap / Urbano Latino": "Trap Latino",
    "Urbano Latino / Trap": "Trap Latino",
    "Trap / Alternative": "Trap",
    "Trap": "Trap",
    "Trap Latino": "Trap Latino",
    "Hip-Hop": "Hip-Hop",
    "Hip-Hop/Rap": "Hip-Hop",
    "Rap/Hip Hop": "Hip-Hop",
    "Rap": "Rap",
    "Latin Rap": "Rap Latino",
    "Alternative Rap": "Hip-Hop Alternativo",
    "Alternative / Hip-Hop": "Hip-Hop Alternativo",

    # J-Core & Hardcore subgenres
    "J-Core / Hardcore": "J-Core",
    "Hardcore Techno / J-Core": "J-Core",
    "J-Core / Electronic": "J-Core",
    "Electronic / J-Core": "J-Core",
    "J-Core / Pop": "J-Core",
    "J-Core / Speedcore": "Speedcore",
    "Electronic / Speedcore": "Speedcore",
    "Speedcore / Terrorcore": "Speedcore",
    "Hardcore Techno": "Hardcore Techno",
    "Frenchcore / Hardcore Techno": "Frenchcore",
    "Hardcore Techno / Frenchcore": "Frenchcore",
    "Frenchcore": "Frenchcore",
    "Happy Hardcore": "Happy Hardcore",
    "Hardcore": "Hardcore",
    "J-Core": "J-Core",
    "Speedcore": "Speedcore",

    # Electronic subgenres
    "Electronic": "Electronic",
    "Electro": "Electro",
    "Dance": "Dance",
    "Dance, Électronique": "Dance",
    "Electronic; Dance; Techno": "Techno",
    "Techno": "Techno",
    "Dubstep": "Dubstep",
    "House": "House",
    "Trance": "Trance",
    "Electronic / Chiptune": "Chiptune",
    "Chiptune": "Chiptune",
    "Nightcore": "Nightcore",
    "Pop Electronica": "Electropop",
    "Electronic / Pop": "Electropop",
    "Electropop": "Electropop",
    "Electronic; Latin": "Electronic",

    # Latin & Urbano
    "Urbano latino": "Urbano Latino",
    "Urbano Latino": "Urbano Latino",
    "Latino": "Latino",
    "Latin": "Latino",
    "Reggaeton": "Reggaeton",
    "Pop Latino": "Pop Latino",
    "Música Brasileña": "Música Brasileña",
    "Música tropical": "Música Tropical",
    "Música Tropical": "Música Tropical",
    "Música Mexicana": "Música Mexicana",
    "Modern Dancehall": "Dancehall",
    "Dancehall": "Dancehall",
    "Afrobeats": "Afrobeats",
    "Música africana": "Afrobeats",

    # Pop & R&B
    "Pop": "Pop",
    "Alternative / Pop": "Pop Alternativo",
    "Pop Alternativo": "Pop Alternativo",
    "R&B": "R&B",
    "R&B/Soul": "R&B / Soul",
    "Contemporary R&B": "R&B",
    "R&B / Hip-Hop": "R&B",

    # Asian & Japanese subgenres
    "J-Pop": "J-Pop",
    "Música asiática": "Música Asiática",
    "Música Asiática": "Música Asiática",
    "Shibuya-kei / Electronic": "Shibuya-kei",
    "Shibuya-kei": "Shibuya-kei",
    "Doujin": "Doujin",
    "Anime": "Anime",

    # Rock, Metal & Alternative
    "Alternative": "Alternativo",
    "Alternativo": "Alternativo",
    "Rock y Alternativo": "Rock Alternativo",
    "Rock Alternativo": "Rock Alternativo",
    "Rock": "Rock",
    "Metal": "Metal",
    "Country": "Country",

    # Soundtrack & Game
    "Game": "Soundtrack",
    "Game Soundtrack": "Soundtrack",
    "Game Soundtrack / Electronic": "Soundtrack",
    "Soundtrack": "Soundtrack",
    "Electronic / Soundtrack": "Soundtrack",
    "Music Game Song": "Soundtrack",
    "Películas/Juegos": "Soundtrack",

    # Other
    "Jazz": "Jazz",
    "Instrumental": "Instrumental"
}

# Heurística para canciones no catalogadas en iTunes/Deezer (doujin/remixes/edits underground)
FALLBACK_ARTIST_GENRES = {
    "Laur": "J-Core",
    "Team Grimoire": "J-Core",
    "RoughSketch": "Hardcore Techno",
    "Notebook Records (RoughSketch)": "Hardcore Techno",
    "かめりあ": "J-Core",
    "Tanger": "Speedcore",
    "tn-shi": "Chiptune",
    "FreeTEMPO": "Shibuya-kei",
    "Bardero$": "Hip-Hop",
    "AKRIILA": "Pop Alternativo",
    "Zell": "Trap",
    "S4nx": "Trap",
    "Mikeanyway": "Trap",
    "Minecraft": "Soundtrack",
    "C.R.O": "Urbano Latino"
}


def normalize_genre(genre_raw: str) -> str:
    cleaned = genre_raw.strip()
    return GENRE_MAPPING.get(cleaned, cleaned)


def run_pipeline(directory: str, apply_changes: bool = False):
    print(f"Directorio: {directory}")
    print(f"Modo: {'APLICAR CAMBIOS (--apply)' if apply_changes else 'MODO EN SECO / DRY RUN (--dry-run)'}\n")

    matcher = MetadataMatcher()
    missing_by_album = defaultdict(list)
    total_files = 0
    already_tagged = 0

    # 1. Recorrer archivos y detectar pistas sin género
    for root, _, files in os.walk(directory):
        for f in files:
            if not f.lower().endswith((".opus", ".ogg", ".flac", ".mp3", ".m4a")):
                continue

            total_files += 1
            file_path = os.path.join(root, f)

            try:
                audio = mutagen.File(file_path)
                has_genre = False
                if audio and audio.tags:
                    for k, v in audio.tags.items():
                        if k.lower() in ("genre", "tcon", "\xa9gen") and v:
                            has_genre = True
                            break

                if has_genre:
                    already_tagged += 1
                else:
                    artist = audio.tags.get("artist", ["Unknown"])[0] if audio and audio.tags else "Unknown"
                    album = audio.tags.get("album", ["Unknown"])[0] if audio and audio.tags else "Unknown"
                    title = audio.tags.get("title", [f])[0] if audio and audio.tags else f
                    missing_by_album[(artist, album)].append((file_path, title, audio))
            except Exception as e:
                print(f"[ERROR LECTURA] {file_path}: {e}", file=sys.stderr)

    print(f"Total canciones: {total_files}")
    print(f"Canciones ya etiquetadas: {already_tagged}")
    print(f"Canciones sin etiqueta: {sum(len(t) for t in missing_by_album.values())} distribuidas en {len(missing_by_album)} álbumes/singles\n")

    # 2. Consultar proveedores oficiales y asignar género
    resolved_tracks = 0
    fallback_tracks = 0
    unresolved_tracks = []
    new_assignments = Counter()

    for (artist, album), tracks in missing_by_album.items():
        sample_title = tracks[0][1]
        query = f"{artist} {sample_title}"
        official_genre = None

        # Intento 1: iTunes
        try:
            res = matcher.itunes.search(query, limit=1)
            if res and res[0].genre:
                official_genre = res[0].genre
        except Exception:
            pass

        # Intento 2: Deezer
        if not official_genre:
            try:
                res_d = matcher.deezer.search(query, limit=1)
                if res_d and res_d[0].genre:
                    official_genre = res_d[0].genre
            except Exception:
                pass

        # Normalizar o usar fallback
        final_genre = None
        if official_genre:
            final_genre = normalize_genre(official_genre)
            resolved_tracks += len(tracks)
        else:
            # Buscar en fallback de artistas conocidos
            for known_art, known_gen in FALLBACK_ARTIST_GENRES.items():
                if known_art.lower() in artist.lower():
                    final_genre = known_gen
                    fallback_tracks += len(tracks)
                    break

        if final_genre:
            new_assignments[final_genre] += len(tracks)
            for file_path, _, audio in tracks:
                if apply_changes:
                    try:
                        audio["genre"] = [final_genre]
                        audio.save()
                    except Exception as e:
                        print(f"[ERROR ESCRITURA] {file_path}: {e}", file=sys.stderr)
        else:
            for file_path, title, _ in tracks:
                unresolved_tracks.append((artist, album, title, file_path))

    # 3. Resumen y verificación final
    print("=" * 60)
    print("REPORTE DE ASIGNACIÓN Y NORMALIZACIÓN")
    print("=" * 60)
    print(f"Recuperadas vía iTunes/Deezer oficiales: {resolved_tracks}")
    print(f"Resueltas por discografía underground:  {fallback_tracks}")
    print(f"Pistas aún sin género detectable:       {len(unresolved_tracks)}")

    if unresolved_tracks:
        print("\n--- PISTAS PENDIENTES SIN GÉNERO ---")
        for art, alb, tit, _ in unresolved_tracks:
            print(f"  - {art} - {tit} [{alb}]")

    # 4. Distribución global de la biblioteca
    print("\n" + "=" * 60)
    print("DISTRIBUCIÓN TOTAL DE GÉNEROS (PREVISTA / RESULTANTE)")
    print("=" * 60)
    
    # Recalcular conteo total si aplicamos o simulamos
    full_counts = Counter()
    for root, _, files in os.walk(directory):
        for f in files:
            if not f.lower().endswith((".opus", ".ogg", ".flac", ".mp3", ".m4a")):
                continue
            audio = mutagen.File(os.path.join(root, f))
            g_val = None
            if audio and audio.tags:
                for k, v in audio.tags.items():
                    if k.lower() in ("genre", "tcon", "\xa9gen") and v:
                        g_val = v[0] if isinstance(v, list) else str(v)
                        break
            if g_val:
                full_counts[normalize_genre(g_val)] += 1
            else:
                full_counts["<SIN GÉNERO>"] += 1

    for g, c in full_counts.most_common():
        print(f"  {c:4d} : {g}")


def main():
    parser = argparse.ArgumentParser(description="Recuperador y normalizador oficial de géneros en Apolo")
    parser.add_argument("--dir", default="/home/hypr/Music/Apolo", help="Ruta de la biblioteca de música")
    parser.add_argument("--apply", action="store_true", help="Aplica los cambios directamente a los archivos")
    args = parser.parse_args()

    run_pipeline(args.dir, apply_changes=args.apply)


if __name__ == "__main__":
    main()
