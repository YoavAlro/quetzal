"""Launch the local management UI.

Usage:
    uv run python -m quetzal.ui            # http://127.0.0.1:8765
    uv run python -m quetzal.ui --port 9000
"""

from __future__ import annotations

import click
import uvicorn


@click.command()
@click.option("--host", default="127.0.0.1", help="Bind host (keep local).")
@click.option("--port", "-p", default=8765, type=int, help="Bind port.")
@click.option("--reload", is_flag=True, help="Auto-reload on code changes (dev).")
def main(host: str, port: int, reload: bool) -> None:
    """Serve the Quetzal console locally."""
    click.echo(f"Quetzal console → http://{host}:{port}")
    uvicorn.run("quetzal.ui.app:app", host=host, port=port, reload=reload, log_level="warning")


if __name__ == "__main__":
    main()
