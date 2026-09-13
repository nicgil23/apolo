import base64
import io
from pathlib import Path
from typing import Optional
import mutagen
from mutagen.oggopus import OggOpus
from mutagen.flac import Picture
from PIL import Image

from apolo.metadata.models import TrackMetadata


class AudioTagger:
    @staticmethod
    def extract_cover_art_from_file(file_path: Path) -> Optional[bytes]:
        """
        Extracts embedded front cover art bytes from an existing audio file (FLAC, MP3, MP4, Opus, Ogg).
        """
        if not file_path.exists():
            return None
        try:
            audio = mutagen.File(file_path)
            if audio is None:
                return None

            tags = getattr(audio, "tags", None)

            # 1. FLAC / OGG pictures attribute
            if hasattr(audio, "pictures") and audio.pictures:
                for pic in audio.pictures:
                    if pic.data:
                        return pic.data

            # 2. Vorbis METADATA_BLOCK_PICTURE
            if tags and "METADATA_BLOCK_PICTURE" in tags:
                try:
                    raw_b64 = tags["METADATA_BLOCK_PICTURE"][0]
                    pic_bytes = base64.b64decode(raw_b64)
                    pic = Picture(pic_bytes)
                    if pic.data:
                        return pic.data
                except Exception:
                    pass

            # 3. ID3 (MP3 / AIFF) APIC frame
            if tags and hasattr(tags, "getall"):
                apics = tags.getall("APIC")
                if apics:
                    # Prefer front cover type 3 if available
                    for apic in apics:
                        if getattr(apic, "type", None) == 3 and apic.data:
                            return apic.data
                    if apics[0].data:
                        return apics[0].data

            # 4. MP4 / M4A covr atom
            if tags and hasattr(tags, "__contains__") and "covr" in tags:
                covr_list = tags["covr"]
                if covr_list and isinstance(covr_list, list) and len(covr_list) > 0:
                    covr_data = covr_list[0]
                    if isinstance(covr_data, (bytes, bytearray)):
                        return bytes(covr_data)
        except Exception:
            pass
        return None

    @staticmethod
    def tag_opus(file_path: Path, metadata: TrackMetadata) -> None:
        """
        Tags an .opus audio file with METADATOS_BIBLIOTECA using Vorbis comments
        and embeds high quality cover art in METADATA_BLOCK_PICTURE.
        """
        try:
            audio = OggOpus(file_path)
        except Exception:
            # If tags don't exist yet, initialize them
            audio = OggOpus(file_path)
            if audio.tags is None:
                audio.add_tags()

        # Clear or set standard Vorbis comment fields
        if metadata.title:
            audio["TITLE"] = [metadata.title]
        if metadata.artist:
            audio["ARTIST"] = [metadata.artist]
        if metadata.album_artist or metadata.artist:
            audio["ALBUMARTIST"] = [metadata.album_artist or metadata.artist]
        if metadata.album:
            audio["ALBUM"] = [metadata.album]
        if metadata.track_number is not None:
            audio["TRACKNUMBER"] = [str(metadata.track_number)]
        if metadata.track_total is not None:
            audio["TRACKTOTAL"] = [str(metadata.track_total)]
        if metadata.date:
            audio["DATE"] = [str(metadata.date)]
        if metadata.genre:
            audio["GENRE"] = [metadata.genre]
        if metadata.disc_number is not None:
            audio["DISCNUMBER"] = [str(metadata.disc_number)]
        if metadata.disc_total is not None:
            audio["DISCTOTAL"] = [str(metadata.disc_total)]
        if metadata.compilation is not None:
            audio["COMPILATION"] = ["1" if metadata.compilation else "0"]
        if metadata.synced_lyrics:
            audio["LYRICS"] = [metadata.synced_lyrics]
        if metadata.origin:
            audio["ORIGIN"] = [metadata.origin]
            audio["SOURCE"] = [metadata.origin]
            audio["ORIGEN"] = [metadata.origin]

        # Embed cover art
        if metadata.cover_art_data:
            try:
                pic = Picture()
                pic.data = metadata.cover_art_data
                pic.type = 3  # Cover (front)

                with Image.open(io.BytesIO(metadata.cover_art_data)) as img:
                    pic.width, pic.height = img.size
                    pic.depth = 24
                    pic.mime = Image.MIME.get(img.format, "image/jpeg")

                picture_data = pic.write()
                encoded_data = base64.b64encode(picture_data).decode("ascii")
                audio["METADATA_BLOCK_PICTURE"] = [encoded_data]
            except Exception:
                pass

        audio.save()

    @staticmethod
    def tag_flac(file_path: Path, metadata: TrackMetadata) -> None:
        """
        Tags a .flac audio file with METADATOS_BIBLIOTECA using native Vorbis comments
        and embeds high quality cover art in FLAC pictures.
        """
        from mutagen.flac import FLAC
        try:
            audio = FLAC(file_path)
        except Exception:
            return

        if metadata.title:
            audio["TITLE"] = [metadata.title]
        if metadata.artist:
            audio["ARTIST"] = [metadata.artist]
        if metadata.album_artist or metadata.artist:
            audio["ALBUMARTIST"] = [metadata.album_artist or metadata.artist]
        if metadata.album:
            audio["ALBUM"] = [metadata.album]
        if metadata.track_number is not None:
            audio["TRACKNUMBER"] = [str(metadata.track_number)]
        if metadata.track_total is not None:
            audio["TRACKTOTAL"] = [str(metadata.track_total)]
        if metadata.date:
            audio["DATE"] = [str(metadata.date)]
        if metadata.genre:
            audio["GENRE"] = [metadata.genre]
        if metadata.disc_number is not None:
            audio["DISCNUMBER"] = [str(metadata.disc_number)]
        if metadata.disc_total is not None:
            audio["DISCTOTAL"] = [str(metadata.disc_total)]
        if metadata.compilation is not None:
            audio["COMPILATION"] = ["1" if metadata.compilation else "0"]
        if metadata.synced_lyrics:
            audio["LYRICS"] = [metadata.synced_lyrics]
        if metadata.origin:
            audio["ORIGIN"] = [metadata.origin]
            audio["SOURCE"] = [metadata.origin]
            audio["ORIGEN"] = [metadata.origin]

        # Embed cover art
        if metadata.cover_art_data:
            try:
                pic = Picture()
                pic.data = metadata.cover_art_data
                pic.type = 3  # Cover (front)

                with Image.open(io.BytesIO(metadata.cover_art_data)) as img:
                    pic.width, pic.height = img.size
                    pic.depth = 24
                    pic.mime = Image.MIME.get(img.format, "image/jpeg")

                audio.clear_pictures()
                audio.add_picture(pic)
            except Exception:
                pass

        audio.save()

    @staticmethod
    def tag_audio(file_path: Path, metadata: TrackMetadata) -> None:
        """Dispatches tagging to appropriate handler based on file extension (.opus or .flac)."""
        suffix = file_path.suffix.lower()
        if suffix == ".flac":
            AudioTagger.tag_flac(file_path, metadata)
        else:
            AudioTagger.tag_opus(file_path, metadata)

    @staticmethod
    def update_tags(
        file_path: Path,
        updates: dict,
        cover_data: Optional[bytes] = None,
    ) -> None:
        """
        Updates specific Vorbis tags and/or cover art on an .opus file without wiping unmentioned tags.
        Supported keys in updates:
          - title, artist, album_artist, album, track_number, track_total,
            date, genre, disc_number, disc_total, compilation, lyrics, origin
        """
        if not file_path.exists():
            return

        try:
            audio = OggOpus(file_path)
        except Exception:
            audio = OggOpus(file_path)
            if audio.tags is None:
                audio.add_tags()

        if "title" in updates and updates["title"] is not None:
            audio["TITLE"] = [str(updates["title"])]
        if "artist" in updates and updates["artist"] is not None:
            audio["ARTIST"] = [str(updates["artist"])]
        if "album_artist" in updates and updates["album_artist"] is not None:
            audio["ALBUMARTIST"] = [str(updates["album_artist"])]
        if "album" in updates and updates["album"] is not None:
            audio["ALBUM"] = [str(updates["album"])]
        if "track_number" in updates and updates["track_number"] is not None:
            audio["TRACKNUMBER"] = [str(updates["track_number"])]
        if "track_total" in updates and updates["track_total"] is not None:
            audio["TRACKTOTAL"] = [str(updates["track_total"])]
        if "date" in updates and updates["date"] is not None:
            audio["DATE"] = [str(updates["date"])]
        if "genre" in updates and updates["genre"] is not None:
            audio["GENRE"] = [str(updates["genre"])]
        if "disc_number" in updates and updates["disc_number"] is not None:
            audio["DISCNUMBER"] = [str(updates["disc_number"])]
        if "disc_total" in updates and updates["disc_total"] is not None:
            audio["DISCTOTAL"] = [str(updates["disc_total"])]
        if "compilation" in updates and updates["compilation"] is not None:
            audio["COMPILATION"] = ["1" if updates["compilation"] else "0"]
        if "lyrics" in updates and updates["lyrics"] is not None:
            audio["LYRICS"] = [str(updates["lyrics"])]
        if "origin" in updates and updates["origin"] is not None:
            audio["ORIGIN"] = [str(updates["origin"])]
            audio["SOURCE"] = [str(updates["origin"])]
            audio["ORIGEN"] = [str(updates["origin"])]

        if cover_data:
            try:
                pic = Picture()
                pic.data = cover_data
                pic.type = 3  # Cover (front)

                with Image.open(io.BytesIO(cover_data)) as img:
                    pic.width, pic.height = img.size
                    pic.depth = 24
                    pic.mime = Image.MIME.get(img.format, "image/jpeg")

                picture_data = pic.write()
                encoded_data = base64.b64encode(picture_data).decode("ascii")
                audio["METADATA_BLOCK_PICTURE"] = [encoded_data]
            except Exception:
                pass

        audio.save()

