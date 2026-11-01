import typer
from rich.panel import Panel

from apolo.cli.ui import console
from apolo.config import load_config
from apolo.services.server import ApoloServer


def register(app: typer.Typer) -> None:
    @app.command(name="serve")
    def serve(
        host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host address to bind the API server to"),
        port: int = typer.Option(4533, "--port", "-p", help="Port to listen on for REST requests"),
    ):
        """
        [bold green]Start the Apolo Local REST API Server[/bold green] for browser and desktop plugins (YouTube, Spicetify).

        Listens on [cyan]http://127.0.0.1:4533[/cyan] by default and processes queued downloads in the background.
        """
        config = load_config()
        server = ApoloServer(host=host, port=port, config=config)

        console.print(
            Panel(
                f"[bold green]Apolo REST API Server active[/bold green]\n\n"
                f"• Listening on: [bold cyan]http://{host}:{port}[/bold cyan]\n"
                f"• Endpoints: [yellow]GET /api/status[/yellow], [yellow]POST /api/download[/yellow], [yellow]GET /api/tasks[/yellow]\n"
                f"• Ready to receive requests from YouTube, YouTube Music and Spicetify plugins.\n\n"
                f"[dim]Press Ctrl+C to stop the server[/dim]",
                title="Apolo Daemon Server",
                border_style="green",
            )
        )

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping Apolo REST API Server...[/yellow]")
            server.shutdown()
            console.print("[green]Server stopped successfully.[/green]")
