import base64
import io
from pathlib import Path
from typing import Optional
from mutagen.oggopus import OggOpus
from mutagen.flac import Picture
from PIL import Image

from apolo.metadata.models import TrackMetadata


class AudioTagger:
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
