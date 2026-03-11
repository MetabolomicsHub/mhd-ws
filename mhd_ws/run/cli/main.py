"""MHD CLI tool entry point."""

from __future__ import annotations

import click

from mhd_ws.run.cli.announcement.derive_announcement import derive_announcement
from mhd_ws.run.cli.announcement.load_announcement import load_announcement
from mhd_ws.run.cli.announcement.seed_datasets import seed_datasets
from mhd_ws.run.cli.indexing.index_datasets import index_datasets


@click.group()
@click.version_option(package_name="mhd-ws")
def mhd_tool() -> None:
    """MHD CLI tool for dataset indexing and maintenance tasks."""


mhd_tool.add_command(index_datasets)
mhd_tool.add_command(derive_announcement)
mhd_tool.add_command(load_announcement)
mhd_tool.add_command(seed_datasets)


if __name__ == "__main__":
    mhd_tool()
