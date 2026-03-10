"""CLI command for deriving announcement files from .mhd.json files."""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

import click

from mhd_ws.infrastructure.search.indexing.utils import eprint
from mhd_ws.run.cli.announcement.containers import AnnouncementCliContainer
from mhd_ws.run.config_renderer import render_config_secrets

logger = logging.getLogger(__name__)


@click.command(name="derive-announcement")
@click.argument("accession")
@click.option(
    "--mhd-file",
    "mhd_file_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    required=True,
    help="Path to the .mhd.json file to convert.",
)
@click.option(
    "--mhd-url",
    "mhd_file_url",
    default=None,
    help=(
        "Public URL of the mhd.json file (embedded in the announcement). "
        "If omitted, uses {mhd-file-base-url}/{accession}.mhd.json."
    ),
)
@click.option(
    "--mhd-file-base-url",
    default=None,
    envvar="MHD_FILE_BASE_URL",
    help="Base URL for constructing mhd.json URLs. Also read from MHD_FILE_BASE_URL env var.",
)
@click.option(
    "--reason",
    default="Derived from mhd.json via CLI",
    help="Reason stored in DatasetRevision.description.",
)
@click.option(
    "--config-file",
    type=click.Path(exists=True),
    required=True,
    help="YAML config file (for DB connection).",
)
@click.option(
    "--secrets-file",
    type=click.Path(exists=True),
    default=None,
    help="YAML secrets file.",
)
def derive_announcement(
    accession: str,
    mhd_file_path: str,
    mhd_file_url: str | None,
    mhd_file_base_url: str | None,
    reason: str,
    config_file: str,
    secrets_file: str | None,
) -> None:
    """Derive an announcement file from a .mhd.json file and store it in Postgres.

    ACCESSION is the MHD accession number (e.g. MHD000001).

    Examples:

    \b
    mhd derive-announcement MHD000001 \\
        --mhd-file /data/MHD000001.mhd.json \\
        --mhd-file-base-url https://cdn.example.com/datasets \\
        --config-file config/local.yml
    """
    # Resolve mhd.json URL (embedded in the announcement output — not fetched)
    if not mhd_file_url:
        if not mhd_file_base_url:
            raise click.ClickException(
                "Either --mhd-url or --mhd-file-base-url (or MHD_FILE_BASE_URL env var) is required."
            )
        mhd_file_url = f"{mhd_file_base_url.rstrip('/')}/{accession}.mhd.json"

    # Load mhd.json from disk
    p = Path(mhd_file_path)
    try:
        mhd_file_json: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise click.ClickException(f"Failed to parse {p}: {e}") from e

    # Set up DI container
    container = AnnouncementCliContainer()
    container.config.from_yaml(config_file)
    if secrets_file:
        container.secrets.from_yaml(secrets_file)
    render_config_secrets(container.config(), container.secrets())
    container.init_resources()

    db_client = container.gateways.database_client()

    from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.tasks import (
        derive_announcement as _derive,
    )

    async def _run() -> None:
        result = await _derive(
            accession=accession,
            mhd_file_url=mhd_file_url,
            mhd_file=mhd_file_json,
            reason=reason,
            database_client=db_client,
            cache_service=None,
        )
        if result.get("success"):
            eprint(f"SUCCESS: {result['message']}")
        else:
            eprint(f"ERROR: {result['message']}")
            sys.exit(1)

    asyncio.run(_run())
