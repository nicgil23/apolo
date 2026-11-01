from pathlib import Path

import typer
from rich.table import Table

from apolo.cli.ui import console
from apolo.tagging.cover import CoverManager


def register(app: typer.Typer) -> None:
    cover_app = typer.Typer(
        name="cover",
        help="""[bold green]Cover Art Utilities[/bold green]: Extract embedded covers to cover.jpg/folder.jpg for media servers or embed custom covers.""",
        no_args_is_help=True,
        rich_markup_mode="rich",
    )
    app.add_typer(cover_app, name="cover")

    @cover_app.command(name="extract")
    def cover_extract_cmd(
        paths: list[Path] = typer.Argument(
            ...,
            help="Audio file(s) or directories to extract cover art from",
        ),
        filename: str = typer.Option(
            "cover.jpg",
            "--name",
            "-n",
            help="Target image filename (e.g. cover.jpg or folder.jpg)",
        ),
        overwrite: bool = typer.Option(
            False,
            "--overwrite",
            "-f",
            help="Overwrite existing cover image files",
        ),
    ):
        """[bold green]Extract Cover Art[/bold green]: Save embedded cover art as cover.jpg / folder.jpg in each album directory for media servers."""
        extracted = CoverManager.extract_covers(
            paths, target_filename=filename, overwrite=overwrite
        )
        if not extracted:
            console.print(
                "[yellow]No embedded covers extracted (already exist or not found).[/yellow]"
            )
            return

        table = Table(
            title=f"Extracted Cover Art ({len(extracted)} saved)",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Source Track", style="dim")
        table.add_column("Extracted Image", style="green")
        for src, out_img in extracted:
            table.add_row(src.name, f"{out_img.parent.name}/{out_img.name}")
        console.print(table)

    @cover_app.command(name="set")
    def cover_set_cmd(
        paths: list[Path] = typer.Argument(
            ...,
            help="Audio file(s) or directories to update with new cover art",
        ),
        image: Path = typer.Argument(
            ...,
            help="Path to high-resolution image file to embed",
        ),
    ):
        """[bold green]Set Album Cover[/bold green]: Embed an optimized 1:1 square cover art image into all audio tracks in a directory."""
        try:
            updated = CoverManager.set_album_cover(paths, image)
            console.print(
                f"[bold green]Successfully embedded cover art into {updated} tracks.[/bold green]"
            )
        except Exception as e:
            console.print(f"[bold red]Error embedding cover art:[/bold red] {e}")
            raise typer.Exit(code=1)
