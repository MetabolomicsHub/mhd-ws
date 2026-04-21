"""CLI command for indexing MHD datasets into Elasticsearch."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

import click

from mhd_ws.infrastructure.search.indexing.dataset_builder import (
    build_legacy_dataset_doc,
)
from mhd_ws.infrastructure.search.indexing.io_utils import (
    iter_input_files,
    write_bulk,
    write_json_dir,
    write_jsonl,
)
from mhd_ws.infrastructure.search.indexing.metabolite_builder import (
    build_metabolite_docs,
)
from mhd_ws.infrastructure.search.indexing.utils import (
    eprint,
    iso_now,
    load_json_file,
)
from mhd_ws.run.cli.indexing.containers import IndexingCliContainer
from mhd_ws.run.config_renderer import render_config_secrets

logger = logging.getLogger(__name__)


def _default_index_name() -> str:
    return os.getenv("MHD_INDEX_NAME") or "dataset_ms_v1"


def _default_metabolite_index_name() -> str:
    return os.getenv("MHD_METABOLITE_INDEX_NAME") or "metabolite_ms_v1"


def _ensure_cli_logging(
    config: dict[str, Any], secrets: dict[str, Any] | None = None
) -> None:
    run_cfg = config.get("run") or {}
    cli_cfg = run_cfg.get("cli") or {}
    if cli_cfg.get("logging"):
        return
    logging_cfg = (run_cfg.get("mhd_ws") or {}).get("logging")
    if not logging_cfg and secrets:
        logging_cfg = ((secrets.get("run") or {}).get("cli") or {}).get("logging")
        if not logging_cfg:
            logging_cfg = ((secrets.get("run") or {}).get("mhd_ws") or {}).get(
                "logging"
            )
    if logging_cfg:
        cli_cfg["logging"] = logging_cfg
        run_cfg["cli"] = cli_cfg
        config["run"] = run_cfg


def _resolve_repo_path(path_str: str) -> str:
    path = Path(path_str)
    if path.is_absolute():
        return str(path)
    if path.exists():
        return str(path)
    repo_root = Path(__file__).resolve().parents[4]
    candidate = repo_root / path
    if candidate.exists():
        return str(candidate)
    return str(path)


def log_facets(
    doc: dict[str, Any],
    facet_keys: list[str],
    log_values: bool,
) -> None:
    for k in facet_keys:
        vals = doc.get("facets", {}).get(k, [])
        if log_values:
            eprint(f"FACET {doc.get('id')} {k} = {vals}")
        else:
            eprint(f"FACET {doc.get('id')} {k} count={len(vals)}")
    orgs = doc.get("organizations", [])
    if log_values:
        eprint(f"ORGS {doc.get('id')} = {orgs}")
    else:
        eprint(f"ORGS {doc.get('id')} count={len(orgs)}")


def build_docs(
    files: list[Path],
    skip_metabolites: bool,
    facet_keys: list[str] | None,
    log_facet_values: bool,
    indexed_ts: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[tuple[str, str]]]:
    docs: list[dict[str, Any]] = []
    metabolite_docs: list[dict[str, Any]] = []
    errors: list[tuple[str, str]] = []

    for p in files:
        try:
            mhd = load_json_file(p)
            doc = build_legacy_dataset_doc(mhd, indexed_ts)
            docs.append(doc)
            if not skip_metabolites:
                metabolite_docs.extend(build_metabolite_docs(mhd, doc))
            if facet_keys:
                log_facets(doc, facet_keys, log_facet_values)
        except Exception as e:
            errors.append((str(p), str(e)))

    return docs, metabolite_docs, errors


def summarize(
    files: list[Path],
    docs: list[dict[str, Any]],
    metabolite_docs: list[dict[str, Any]],
    errors: list[tuple[str, str]],
    skip_metabolites: bool,
) -> None:
    eprint(f"Processed files: {len(files)}")
    eprint(f"Built dataset docs:    {len(docs)}")
    if not skip_metabolites:
        eprint(f"Built metabolite docs: {len(metabolite_docs)}")
    eprint(f"Errors:          {len(errors)}")
    if errors:
        eprint("---- Errors ----")
        for fp, msg in errors:
            eprint(f"{fp}: {msg}")


async def _handle_upload(
    docs: list[dict[str, Any]],
    metabolite_docs: list[dict[str, Any]],
    es_client,
    index_name: str,
    metabolite_index: str,
    mapping_file: str,
    metabolite_mapping_file: str,
    op_type: str,
    batch_size: int,
    recreate_index: bool,
    skip_metabolites: bool,
) -> None:
    await es_client.start()
    try:
        mapping_path = Path(mapping_file)
        if not mapping_path.is_file():
            raise click.ClickException(f"mapping file does not exist: {mapping_path}")
        mapping = load_json_file(mapping_path)
        await es_client.ensure_index_exists(
            index_name,
            mapping,
            recreate=recreate_index,
            api_key_name="dataset_ms",
        )
        n = await es_client.bulk_upload(
            docs,
            index_name=index_name,
            op_type=op_type,
            batch_size=batch_size,
            api_key_name="dataset_ms",
        )
        eprint(f"Uploaded {n} dataset docs to index {index_name}")

        if not skip_metabolites:
            metab_mapping_path = Path(metabolite_mapping_file)
            if not metab_mapping_path.is_file():
                raise click.ClickException(
                    f"metabolite mapping file does not exist: {metab_mapping_path}"
                )
            metab_mapping = load_json_file(metab_mapping_path)
            await es_client.ensure_index_exists(
                metabolite_index,
                metab_mapping,
                recreate=recreate_index,
                api_key_name="metabolite",
            )
            n_met = await es_client.bulk_upload(
                metabolite_docs,
                index_name=metabolite_index,
                op_type=op_type,
                batch_size=batch_size,
                api_key_name="metabolite",
            )
            eprint(f"Uploaded {n_met} metabolite docs to index {metabolite_index}")
    finally:
        await es_client.close()


def handle_output(
    docs: list[dict[str, Any]],
    metabolite_docs: list[dict[str, Any]],
    fmt: str,
    out: str,
    json_dir: str | None,
    index_name: str,
    metabolite_index: str,
    op_type: str,
    skip_metabolites: bool,
) -> None:
    if fmt == "json-dir":
        if not json_dir:
            raise click.ClickException("--json-dir is required when --format json-dir")
        out_dir = Path(json_dir)
        n = write_json_dir(out_dir, docs)
        eprint(f"Wrote {n} dataset JSON files to {out_dir}")
        if not skip_metabolites:
            metab_dir = out_dir / "metabolites"
            n_met = write_json_dir(metab_dir, metabolite_docs)
            eprint(f"Wrote {n_met} metabolite JSON files to {metab_dir}")
        return

    if out == "-":
        out_fh = sys.stdout
        close = False
    else:
        out_fh = open(out, "w", encoding="utf-8")  # noqa: SIM115, PTH123
        close = True

    try:
        if fmt == "bulk":
            n = write_bulk(out_fh, docs, index_name=index_name, op_type=op_type)
            eprint(f"Wrote bulk payload for {n} dataset docs")
            if not skip_metabolites:
                n_met = write_bulk(
                    out_fh,
                    metabolite_docs,
                    index_name=metabolite_index,
                    op_type=op_type,
                )
                eprint(f"Wrote bulk payload for {n_met} metabolite docs")
        elif fmt == "jsonl":
            n = write_jsonl(out_fh, docs)
            eprint(f"Wrote {n} JSONL dataset docs")
            if not skip_metabolites:
                n_met = write_jsonl(out_fh, metabolite_docs)
                eprint(f"Wrote {n_met} JSONL metabolite docs")
    finally:
        if close:
            out_fh.close()


@click.command(name="index")
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--config-file",
    type=click.Path(exists=True),
    default=None,
    help="YAML config file (for ES connection when --upload is set)",
)
@click.option(
    "--secrets-file",
    type=click.Path(exists=True),
    default=None,
    help="YAML secrets file",
)
@click.option("--pattern", default="*.mhd.json", help="Glob pattern within input_dir")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["bulk", "jsonl", "json-dir"]),
    default="bulk",
    help="Output format",
)
@click.option(
    "--out", default="-", help="Output file path, or '-' for stdout (bulk/jsonl only)"
)
@click.option("--json-dir", default=None, help="Output directory for --format json-dir")
@click.option(
    "--index",
    "index_name",
    default=_default_index_name,
    help="ES index name for dataset documents",
)
@click.option(
    "--metabolite-index",
    default=_default_metabolite_index_name,
    help="ES index name for metabolite documents",
)
@click.option(
    "--mapping-file",
    default="resources/es/mappings/ms_mapping.json",
    help="Index mapping JSON for dataset index",
)
@click.option(
    "--metabolite-mapping-file",
    default="resources/es/mappings/metabolite_mapping.json",
    help="Index mapping JSON for metabolite index",
)
@click.option(
    "--upload", is_flag=True, help="Upload to Elasticsearch using the Bulk API"
)
@click.option(
    "--dry-run", is_flag=True, help="Do not write docs; only print summary/errors"
)
@click.option("--batch-size", type=int, default=500, help="Bulk upload batch size")
@click.option(
    "--recreate-index", is_flag=True, help="Delete and recreate the index before upload"
)
@click.option(
    "--skip-metabolites",
    is_flag=True,
    help="Skip building and indexing metabolite documents",
)
@click.option(
    "--max-files", type=int, default=0, help="Process at most N files (0 = no limit)"
)
@click.option(
    "--log-facets", is_flag=True, help="Log facet values per document to stderr"
)
@click.option(
    "--log-facet-keys",
    default="diseases,sample_types",
    help="Comma-separated facet keys to log with --log-facets",
)
@click.option(
    "--log-facet-values",
    is_flag=True,
    help="Log full facet values (default logs counts only)",
)
def index_datasets(  # noqa: PLR0913
    input_dir: str,
    config_file: str | None,
    secrets_file: str | None,
    pattern: str,
    fmt: str,
    out: str,
    json_dir: str | None,
    index_name: str,
    metabolite_index: str,
    mapping_file: str,
    metabolite_mapping_file: str,
    upload: bool,
    dry_run: bool,
    batch_size: int,
    recreate_index: bool,
    skip_metabolites: bool,
    max_files: int,
    log_facets: bool,
    log_facet_keys: str,
    log_facet_values: bool,
) -> None:
    """Index MHD datasets (.mhd.json) into Elasticsearch documents."""

    input_path = Path(input_dir)
    files = iter_input_files(input_path, pattern)
    if max_files and max_files > 0:
        files = files[:max_files]

    if not files:
        raise click.ClickException(f"no files matched {pattern} in {input_path}")

    facet_keys = (
        [k.strip() for k in log_facet_keys.split(",") if k.strip()]
        if log_facets
        else None
    )

    indexed_ts = iso_now()
    docs, metabolite_docs, errors = build_docs(
        files, skip_metabolites, facet_keys, log_facet_values, indexed_ts
    )

    summarize(files, docs, metabolite_docs, errors, skip_metabolites)

    if dry_run:
        raise SystemExit(0 if docs else 1)

    if upload:
        if not config_file:
            raise click.ClickException("--config-file is required when --upload is set")
        container = IndexingCliContainer()
        container.config.from_yaml(config_file)
        if secrets_file:
            container.secrets.from_yaml(secrets_file)
        render_config_secrets(container.config(), container.secrets())
        _ensure_cli_logging(container.config(), container.secrets())
        mapping_file = _resolve_repo_path(mapping_file)
        metabolite_mapping_file = _resolve_repo_path(metabolite_mapping_file)

        container.init_resources()
        es_client = container.gateways.elasticsearch_client()

        asyncio.run(
            _handle_upload(
                docs,
                metabolite_docs,
                es_client,
                index_name=index_name,
                metabolite_index=metabolite_index,
                mapping_file=mapping_file,
                metabolite_mapping_file=metabolite_mapping_file,
                op_type="index",
                batch_size=batch_size,
                recreate_index=recreate_index,
                skip_metabolites=skip_metabolites,
            )
        )
        return

    handle_output(
        docs,
        metabolite_docs,
        fmt=fmt,
        out=out,
        json_dir=json_dir,
        index_name=index_name,
        metabolite_index=metabolite_index,
        op_type="index",
        skip_metabolites=skip_metabolites,
    )
