"""MHD CLI tool entry point."""

from __future__ import annotations

import click

from mhd_ws.run.cli.indexing.index_datasets import index_datasets


@click.group()
@click.version_option(package_name="mhd-ws")
def mhd_tool() -> None:
    """MHD CLI tool for dataset indexing and maintenance tasks."""


mhd_tool.add_command(index_datasets)


if __name__ == "__main__":
    mhd_tool()
