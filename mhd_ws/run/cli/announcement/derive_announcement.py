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


async def _run_derive(
    accession: str,
    mhd_file_json: dict[str, Any],
    mhd_file_url: str,
    reason: str,
    db_client: Any,
) -> bool:
    """Derive and store one announcement. Returns True on success."""
    from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.tasks import (
        derive_announcement as _derive,
    )

    result = await _derive(
        accession=accession,
        mhd_file_url=mhd_file_url,
        mhd_file=mhd_file_json,
        reason=reason,
        database_client=db_client,
        cache_service=None,
    )
    if result.get("success"):
        eprint(f"  OK  {accession}: {result['message']}")
        return True
    else:
        eprint(f"  ERR {accession}: {result['message']}")
        return False


@click.command(name="derive-announcement")
@click.argument("accession", required=False, default=None)
@click.option(
    "--mhd-file",
    "mhd_file_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Path to a single .mhd.json file to convert.",
)
@click.option(
    "--dir",
    "mhd_dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=None,
    help="Directory of .mhd.json files. Accession is derived from each filename.",
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
    accession: str | None,
    mhd_file_path: str | None,
    mhd_dir: str | None,
    mhd_file_url: str | None,
    mhd_file_base_url: str | None,
    reason: str,
    config_file: str,
    secrets_file: str | None,
) -> None:
    """Derive announcement file(s) from .mhd.json and store in Postgres.

    Single file mode: provide ACCESSION and --mhd-file.

    \b
    mhd derive-announcement MHD000001 \\
        --mhd-file /data/MHD000001.mhd.json \\
        --mhd-file-base-url https://cdn.example.com \\
        --config-file config/local.yml

    Directory mode: provide --dir. Accession is taken from each filename
    (e.g. MHD000001.mhd.json → MHD000001).

    \b
    mhd derive-announcement \\
        --dir /data/mhd-files/ \\
        --mhd-file-base-url https://cdn.example.com \\
        --config-file config/local.yml
    """
    if mhd_dir and (accession or mhd_file_path):
        raise click.ClickException(
            "--dir cannot be combined with ACCESSION or --mhd-file."
        )
    if not mhd_dir and not mhd_file_path:
        raise click.ClickException(
            "Provide either --mhd-file (with ACCESSION) or --dir."
        )
    if mhd_file_path and not accession:
        raise click.ClickException("ACCESSION is required when using --mhd-file.")

    # Set up DI container
    container = AnnouncementCliContainer()
    container.config.from_yaml(config_file)
    if secrets_file:
        container.secrets.from_yaml(secrets_file)
    render_config_secrets(container.config(), container.secrets())
    container.init_resources()
    db_client = container.gateways.database_client()

    def _resolve_url(acc: str, path: Path) -> str:
        if mhd_file_url:
            return mhd_file_url
        if mhd_file_base_url:
            return f"{mhd_file_base_url.rstrip('/')}/{acc}.mhd.json"
        raise click.ClickException(
            "Either --mhd-url or --mhd-file-base-url (or MHD_FILE_BASE_URL) is required."
        )

    def _load_json(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            raise click.ClickException(f"Failed to parse {path}: {e}") from e

    if mhd_dir:
        files = sorted(Path(mhd_dir).glob("*.mhd.json"))
        if not files:
            raise click.ClickException(f"No *.mhd.json files found in {mhd_dir}")
        eprint(f"Processing {len(files)} file(s) from {mhd_dir} ...")

        async def _run_dir() -> tuple[int, int]:
            ok = err = 0
            for f in files:
                acc = f.name.removesuffix(".mhd.json")
                url = _resolve_url(acc, f)
                if await _run_derive(acc, _load_json(f), url, reason, db_client):
                    ok += 1
                else:
                    err += 1
            return ok, err

        ok, err = asyncio.run(_run_dir())
        eprint(f"Done. {ok} succeeded, {err} failed.")
        if err:
            sys.exit(1)
    else:
        p = Path(mhd_file_path)
        url = _resolve_url(accession, p)

        async def _run_one() -> bool:
            return await _run_derive(accession, _load_json(p), url, reason, db_client)

        if not asyncio.run(_run_one()):
            sys.exit(1)
