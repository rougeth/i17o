import asyncio
from pathlib import Path

import click

from .stats import download_current_stats


@click.group()
def cli():
    ...


@cli.command()
@click.argument("path", type=click.Path(exists=True))
def download_stats(path):
    path = Path(path)
    asyncio.run(download_current_stats(path))


if __name__ == "__main__":
    cli()
