"""CLI command for seeding Dataset rows from .mhd.json files."""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

import click
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mhd_ws.infrastructure.persistence.db.mhd import (
    AccessionType,
    Dataset,
    DatasetStatus,
    Repository,
)
from mhd_ws.infrastructure.search.indexing.utils import eprint
from mhd_ws.run.cli.announcement.containers import AnnouncementCliContainer
from mhd_ws.run.config_renderer import render_config_secrets

logger = logging.getLogger(__name__)


def _strip_suffix(value: str, suffix: str) -> str:
    if value.endswith(suffix):
        return value[: -len(suffix)]
    return value


def _get_accession(data: dict[str, Any], path: Path) -> str:
    """Extract accession from mhd_identifier or repository_identifier, fallback to filename."""
    raw = data.get("mhd_identifier") or data.get("repository_identifier") or path.stem
    raw = _strip_suffix(raw, ".announcement")
    raw = _strip_suffix(raw, ".mhd")
    return raw


def _guess_accession_type(accession: str) -> AccessionType:
    if accession.startswith("MHDT"):
        return AccessionType.TEST_MHD
    if accession.startswith("MHDD"):
        return AccessionType.DEV
    if accession.startswith("MHD"):
        return AccessionType.MHD
    return AccessionType.LEGACY


async def _resolve_repository(
    session: AsyncSession,
    repository_id: int | None,
    repository_name: str | None,
) -> Repository | None:
    if repository_id is not None:
        stmt = select(Repository).where(Repository.id == repository_id).limit(1)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    if repository_name:
        stmt = select(Repository).where(
            (Repository.name.ilike(repository_name))
            | (Repository.short_name.ilike(repository_name))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    return None


async def _seed_one(
    *,
    session: AsyncSession,
    accession: str,
    accession_type: AccessionType,
    repository_identifier: str,
    repository_id: int | None,
    repository_name: str | None,
) -> tuple[bool, str]:
    repo = await _resolve_repository(session, repository_id, repository_name)
    if repo is None:
        return (
            False,
            "Repository not found. Provide --repository-id or ensure repository exists.",
        )

    stmt = select(Dataset).where(Dataset.accession == accession).limit(1)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing is not None:
        return True, "Dataset already exists."

    dataset = Dataset(
        repository=repo,
        accession=accession,
        accession_type=accession_type,
        dataset_repository_identifier=repository_identifier or accession,
        revision=0,
        status=DatasetStatus.PRIVATE,
    )
    session.add(dataset)
    await session.commit()
    return True, "Dataset inserted."


@click.command(name="seed-datasets")
@click.option(
    "--dir",
    "mhd_dir",
    type=click.Path(exists=True, file_okay=False, dir_okay=True),
    required=True,
    help="Directory of .mhd.json files.",
)
@click.option(
    "--repository-id",
    type=int,
    default=None,
    help="Repository id to use for all datasets (overrides repository_name in JSON).",
)
@click.option(
    "--repository-name",
    type=str,
    default=None,
    help="Repository name to use for all datasets (matches repository.name or short_name).",
)
@click.option(
    "--accession-type",
    type=click.Choice([t.value for t in AccessionType]),
    default=None,
    help="Accession type to use for all datasets (default: inferred from accession prefix).",
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
def seed_datasets(
    mhd_dir: str,
    repository_id: int | None,
    repository_name: str | None,
    accession_type: str | None,
    config_file: str,
    secrets_file: str | None,
) -> None:
    """Seed Dataset rows from .mhd.json files for local/test use."""
    container = AnnouncementCliContainer()
    container.config.from_yaml(config_file)
    if secrets_file:
        container.secrets.from_yaml(secrets_file)
    render_config_secrets(container.config(), container.secrets())
    container.init_resources()
    db_client = container.gateways.database_client()

    files = sorted(Path(mhd_dir).glob("*.mhd.json"))
    if not files:
        raise click.ClickException(f"No *.mhd.json files found in {mhd_dir}")

    resolved_accession_type = AccessionType(accession_type) if accession_type else None

    def _load_json(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            raise click.ClickException(f"Failed to parse {path}: {e}") from e

    async def _run_dir() -> tuple[int, int]:
        ok = err = 0
        async with db_client.session() as a_session:
            session: AsyncSession = a_session
            for f in files:
                data = _load_json(f)
                acc = _get_accession(data, f)
                repo_identifier = data.get("repository_identifier") or acc
                repo_name = repository_name or data.get("repository_name")
                acc_type = resolved_accession_type or _guess_accession_type(acc)
                success, message = await _seed_one(
                    session=session,
                    accession=acc,
                    accession_type=acc_type,
                    repository_identifier=repo_identifier,
                    repository_id=repository_id,
                    repository_name=repo_name,
                )
                if success:
                    eprint(f"  OK  {acc}: {message}")
                    ok += 1
                else:
                    eprint(f"  ERR {acc}: {message}")
                    err += 1
        return ok, err

    ok, err = asyncio.run(_run_dir())
    eprint(f"Done. {ok} succeeded, {err} failed.")
    if err:
        sys.exit(1)
