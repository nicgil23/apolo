import re
from pathlib import Path
from typing import Any

from apolo.metadata.models import TrackMetadata
from apolo.metadata.parsing import extract_disc_info
from apolo.storage.sanitize import sanitize_filename, strip_accents

DEFAULT_PATH_TEMPLATE = "{artist}/{album} ({date})/{track:02d} - {title}.opus"


def extract_initial(artist_name: str | None) -> str:
    """Extracts an uppercase alphabetical initial (A-Z) from an artist name, ignoring leading symbols and diacritics.

    Returns '#' for numbers and non-alphabetic names.
    """
    if not artist_name:
        return "#"
    clean = strip_accents(artist_name).strip()
    # Remove leading symbols or punctuation
    clean = re.sub(r"^[^\w]+", "", clean).strip()
    if not clean:
        return "#"
    first = clean[0].upper()
    if "A" <= first <= "Z":
        return first
    return "#"


def extract_decade(year_str: str | None) -> str:
    """Calculates a decade string (e.g. '1980s', '2020s') from a year string."""
    if not year_str:
        return "Unknown Decade"
    match = re.search(r"\b(19\d{2}|20\d{2})\b", str(year_str))
    if match:
        y = int(match.group(1))
        return f"{(y // 10) * 10}s"
    return "Unknown Decade"


class PathTemplateEngine:
    """Engine for rendering dynamic library path templates."""

    AVAILABLE_VARIABLES: set[str] = {
        "artist",
        "album_artist",
        "track_artist",
        "album",
        "title",
        "track",
        "track_total",
        "disc",
        "disc_total",
        "date",
        "year",
        "decade",
        "genre",
        "initial",
        "origin",
        "format",
        "ext",
    }

    def build_context(self, metadata: TrackMetadata, extension: str = ".opus") -> dict[str, Any]:
        """Builds a sanitized variable dictionary from a TrackMetadata instance."""
        clean_ext = extension if extension.startswith(".") else f".{extension}"
        format_str = clean_ext.lstrip(".")

        artist_clean = sanitize_filename(metadata.get_album_artist_or_artist())
        album_artist_clean = sanitize_filename(
            metadata.album_artist or metadata.get_album_artist_or_artist()
        )
        track_artist_clean = sanitize_filename(metadata.artist or "Unknown Artist")

        raw_album = metadata.album or "Single"
        cleaned_album_name, disc_from_album = extract_disc_info(raw_album)
        album_clean = sanitize_filename(cleaned_album_name or raw_album)
        title_clean = sanitize_filename(metadata.title)

        year_str = metadata.get_year()
        date_str = str(metadata.date).strip() if metadata.date else year_str
        decade_str = extract_decade(year_str)

        genre_clean = sanitize_filename(metadata.genre or "Unknown Genre")
        initial_clean = extract_initial(artist_clean)
        origin_clean = sanitize_filename(metadata.origin or "local")

        track_num = metadata.track_number if metadata.track_number is not None else 1
        track_tot = metadata.track_total if metadata.track_total is not None else 1
        disc_num = metadata.disc_number or disc_from_album or 1
        disc_tot = metadata.disc_total if metadata.disc_total is not None else 1

        return {
            "artist": artist_clean,
            "album_artist": album_artist_clean,
            "track_artist": track_artist_clean,
            "album": album_clean,
            "title": title_clean,
            "track": track_num,
            "track_total": track_tot,
            "disc": disc_num,
            "disc_total": disc_tot,
            "date": date_str,
            "year": year_str,
            "decade": decade_str,
            "genre": genre_clean,
            "initial": initial_clean,
            "origin": origin_clean,
            "format": format_str,
            "ext": clean_ext,
        }

    def render_parts(
        self, template: str, metadata: TrackMetadata, extension: str = ".opus"
    ) -> list[str]:
        """Renders a path template into a list of sanitized directory and filename segments."""
        clean_ext = extension if extension.startswith(".") else f".{extension}"
        context = self.build_context(metadata, extension=clean_ext)

        # Normalize slashes and split path parts
        raw_parts = [p.strip() for p in Path(template).parts if p.strip()]
        if not raw_parts:
            raw_parts = [p.strip() for p in Path(DEFAULT_PATH_TEMPLATE).parts if p.strip()]

        rendered_parts: list[str] = []
        for idx, part in enumerate(raw_parts):
            try:
                rendered = part.format(**context)
            except KeyError as e:
                var_name = str(e).strip("'")
                raise ValueError(
                    f"Unknown template variable '{{{var_name}}}'. "
                    f"Available variables: {', '.join(sorted(self.AVAILABLE_VARIABLES))}"
                ) from e
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid format specifier in template part '{part}': {e}") from e

            is_last = idx == len(raw_parts) - 1
            if is_last:
                # Handle audio file extension
                # If rendered part ends with an extension like .opus or .flac, adjust it
                if rendered.lower().endswith(clean_ext.lower()):
                    # Already ends with the target extension
                    filename_clean = sanitize_filename(rendered[: -len(clean_ext)]) + clean_ext
                elif re.search(r"\.(opus|flac|mp3|m4a|ogg|wav)$", rendered, re.IGNORECASE):
                    # Ends with another audio extension, replace with target extension
                    base = re.sub(
                        r"\.(opus|flac|mp3|m4a|ogg|wav)$", "", rendered, flags=re.IGNORECASE
                    )
                    filename_clean = sanitize_filename(base) + clean_ext
                else:
                    filename_clean = sanitize_filename(rendered) + clean_ext
                rendered_parts.append(filename_clean)
            else:
                rendered_parts.append(sanitize_filename(rendered))

        return rendered_parts
