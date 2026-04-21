"""CLI command for loading pre-existing announcement files directly into Postgres."""
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


def _strip_suffix(value: str, suffix: str) -> str:
    if value.endswith(suffix):
        return value[: -len(suffix)]
    return value


def _get_accession(data: dict[str, Any], path: Path) -> str:
    """Extract accession from mhd_identifier field, falling back to filename stem."""
    raw = data.get("mhd_identifier") or path.stem
    while True:
        updated = raw
        updated = _strip_suffix(updated, ".announcement")
        updated = _strip_suffix(updated, ".mhd")
        updated = _strip_suffix(updated, ".md")
        if updated == raw:
            return raw
        raw = updated


def _get_announcement_files(directory: Path) -> list[Path]:
    """Return announcement JSON files, skipping source .mhd.json inputs."""
    return sorted(
        path
        for path in directory.glob("*.json")
        if not path.name.endswith(".mhd.json")
    )


async def _run_load(
    accession: str,
    announcement_json: dict[str, Any],
    reason: str,
    db_client: Any,
) -> bool:
    """Store one pre-existing announcement. Returns True on success."""
    from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.tasks import (
        derive_announcement as _derive,
    )

    result = await _derive(
        accession=accession,
        announcement_file=announcement_json,
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


@click.command(name="load-announcement")
@click.option(
    "--announcement-file",
    "announcement_file_path",
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    default=None,
    help="Path to a single pre-existing announcement JSON file.",
)
@click.option(
    "--dir",
    "announcement_dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    default=None,
    help="Directory of announcement JSON files. Accession read from mhd_identifier in each file.",
)
@click.option(
    "--reason",
    default="Loaded from pre-existing announcement file",
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
def load_announcement(
    announcement_file_path: str | None,
    announcement_dir: str | None,
    reason: str,
    config_file: str,
    secrets_file: str | None,
) -> None:
    """Load pre-existing announcement file(s) directly into Postgres (no conversion).

    Skips the mhd.json → announcement conversion step. Accession is read from
    the mhd_identifier field in each file, falling back to the filename stem.

    Single file:

    \b
    mhd load-announcement \\
        --announcement-file /data/MHD000001_announcement.json \\
        --config-file config/local.yml

    Directory:

    \b
    mhd load-announcement \\
        --dir /data/announcements/ \\
        --config-file config/local.yml
    """
    if not announcement_file_path and not announcement_dir:
        raise click.ClickException("Provide either --announcement-file or --dir.")
    if announcement_file_path and announcement_dir:
        raise click.ClickException("--announcement-file and --dir are mutually exclusive.")

    # Set up DI container
    container = AnnouncementCliContainer()
    container.config.from_yaml(config_file)
    if secrets_file:
        container.secrets.from_yaml(secrets_file)
    render_config_secrets(container.config(), container.secrets())
    container.init_resources()
    db_client = container.gateways.database_client()

    def _load_json(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            raise click.ClickException(f"Failed to parse {path}: {e}") from e

    if announcement_dir:
        files = _get_announcement_files(Path(announcement_dir))
        if not files:
            raise click.ClickException(
                f"No announcement *.json files found in {announcement_dir}"
            )
        eprint(f"Processing {len(files)} file(s) from {announcement_dir} ...")
        async def _run_dir() -> tuple[int, int]:
            ok = err = 0
            for f in files:
                data = _load_json(f)
                acc = _get_accession(data, f)
                if await _run_load(acc, data, reason, db_client):
                    ok += 1
                else:
                    err += 1
            return ok, err

        ok, err = asyncio.run(_run_dir())
        eprint(f"Done. {ok} succeeded, {err} failed.")
        if err:
            sys.exit(1)
    else:
        p = Path(announcement_file_path)
        data = _load_json(p)
        acc = _get_accession(data, p)
        async def _run_one() -> bool:
            return await _run_load(acc, data, reason, db_client)

        if not asyncio.run(_run_one()):
            sys.exit(1)
