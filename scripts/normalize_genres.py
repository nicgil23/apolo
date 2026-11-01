#!/usr/bin/env python3
import os
import sys
import argparse
from collections import Counter
import mutagen

GENRE_MAPPING = {
    # Trap & Hip-Hop / Rap
    "Trap / Hip-Hop": "Trap",
    "Trap / Urbano Latino": "Trap Latino",
    "Urbano Latino / Trap": "Trap Latino",
    "Trap / Alternative": "Trap",
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
    "Happy Hardcore": "Happy Hardcore",
    "Hardcore": "Hardcore",

    # Electronic subgenres
    "Electronic": "Electronic",
    "Electro": "Electro",
    "Dance": "Dance",
    "Dance, Électronique": "Dance",
    "Electronic; Dance; Techno": "Techno",
    "Dubstep": "Dubstep",
    "House": "House",
    "Trance": "Trance",
    "Electronic / Chiptune": "Chiptune",
    "Nightcore": "Nightcore",
    "Pop Electronica": "Electropop",
    "Electronic / Pop": "Electropop",
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
    "Modern Dancehall": "Dancehall",

    # Pop & R&B
    "Pop": "Pop",
    "Alternative / Pop": "Pop Alternativo",
    "R&B": "R&B",
    "R&B/Soul": "R&B / Soul",
    "Contemporary R&B": "R&B",
    "R&B / Hip-Hop": "R&B",

    # Asian & Japanese subgenres
    "J-Pop": "J-Pop",
    "Música asiática": "Música Asiática",
    "Shibuya-kei / Electronic": "Shibuya-kei",
    "Doujin": "Doujin",
    "Anime": "Anime",

    # Rock & Alternative
    "Alternative": "Alternativo",
    "Alternativo": "Alternativo",
    "Rock y Alternativo": "Rock Alternativo",

    # Soundtrack & Game
    "Game": "Soundtrack",
    "Game Soundtrack": "Soundtrack",
    "Game Soundtrack / Electronic": "Soundtrack",
    "Soundtrack": "Soundtrack",
    "Electronic / Soundtrack": "Soundtrack",
    "Music Game Song": "Soundtrack",

    # Other
    "Jazz": "Jazz",
    "Instrumental": "Instrumental"
}


def normalize_genre_tag(current_val: str) -> str:
    cleaned = current_val.strip()
    return GENRE_MAPPING.get(cleaned, cleaned)


def process_library(directory: str, apply_changes: bool = False):
    total_files = 0
    modified_count = 0
    unmapped_count = 0
    already_normal_count = 0
    no_genre_count = 0
    errors_count = 0
    
    genre_counts = Counter()
    unmapped_genres = Counter()

    print(f"Escaneando directorio: {directory}")
    print(f"Modo: {'APLICAR CAMBIOS (--apply)' if apply_changes else 'MODO EN SECO / DRY-RUN (--dry-run)'}\n")

    for root, _, files in os.walk(directory):
        for f in files:
            if not f.lower().endswith((".opus", ".ogg", ".flac", ".mp3", ".m4a")):
                continue

            total_files += 1
            file_path = os.path.join(root, f)

            try:
                audio = mutagen.File(file_path)
                if audio is None:
                    errors_count += 1
                    continue

                genre_val = None
                if audio.tags:
                    for k, v in audio.tags.items():
                        if k.lower() in ("genre", "tcon", "\xa9gen") and v:
                            genre_val = " / ".join(str(x) for x in v) if isinstance(v, list) else str(v)
                            break

                if not genre_val:
                    no_genre_count += 1
                    genre_counts["<SIN GÉNERO>"] += 1
                    continue

                if genre_val in GENRE_MAPPING:
                    normalized = GENRE_MAPPING[genre_val]
                    if normalized != genre_val:
                        modified_count += 1
                        if apply_changes:
                            audio["genre"] = [normalized]
                            audio.save()
                    else:
                        already_normal_count += 1
                    genre_counts[normalized] += 1
                else:
                    unmapped_count += 1
                    unmapped_genres[genre_val] += 1
                    genre_counts[genre_val] += 1

            except Exception as e:
                errors_count += 1
                print(f"[ERROR] {file_path}: {e}", file=sys.stderr)

    print("\n" + "="*50)
    print("RESUMEN DE PROCESAMIENTO")
    print("="*50)
    print(f"Total de archivos analizados: {total_files}")
    print(f"Archivos modificados:         {modified_count}")
    print(f"Archivos ya normalizados:     {already_normal_count}")
    print(f"Archivos sin etiqueta género: {no_genre_count}")
    print(f"Archivos con género no mapeado:{unmapped_count}")
    print(f"Errores de lectura/escritura: {errors_count}")

    if unmapped_genres:
        print("\n[ALERTA] Géneros sin mapear encontrados:")
        for ug, c in unmapped_genres.most_common():
            print(f"  {c:3d} : {ug}")

    print("\n--- DISTRIBUCIÓN RESULTANTE DE GÉNEROS ---")
    for g, count in genre_counts.most_common():
        print(f"  {count:3d} : {g}")


def main():
    parser = argparse.ArgumentParser(description="Normalizador de géneros para Apolo Music Library")
    parser.add_argument("--dir", default="/home/hypr/Music/Apolo", help="Ruta de la biblioteca de música")
    parser.add_argument("--apply", action="store_true", help="Aplica los cambios directamente a los archivos")
    args = parser.parse_args()

    process_library(args.dir, apply_changes=args.apply)


if __name__ == "__main__":
    main()
