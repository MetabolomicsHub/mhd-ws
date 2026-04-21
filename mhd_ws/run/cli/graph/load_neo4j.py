"""CLI command for loading MHD graphs into Neo4j."""

from __future__ import annotations

import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import click
from neo4j import GraphDatabase

from mhd_ws.infrastructure.search.indexing.io_utils import iter_input_files
from mhd_ws.infrastructure.search.indexing.utils import eprint, load_json_file

LABEL_RE = re.compile(r"[^A-Za-z0-9]+")


def _sanitize_token(value: str | None, prefix: str) -> str:
    if not value:
        return f"{prefix}_UNKNOWN"
    cleaned = LABEL_RE.sub("_", value.strip()).strip("_").upper()
    if not cleaned:
        cleaned = f"{prefix}_UNKNOWN"
    if cleaned[0].isdigit():
        cleaned = f"{prefix}_{cleaned}"
    return cleaned


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _coerce_value(value: Any) -> Any:
    if _is_scalar(value):
        return value
    if isinstance(value, list):
        if all(_is_scalar(v) for v in value):
            return [v for v in value if v is not None]
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _coerce_props(props: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in props.items():
        coerced = _coerce_value(value)
        if coerced is None:
            continue
        out[key] = coerced
    return out


def _extract_embedded_relationships(node: dict[str, Any]) -> list[tuple[str, str, str]]:
    source_id = node.get("id")
    if not source_id:
        return []
    rels: list[tuple[str, str, str]] = []
    for key, value in node.items():
        if key.endswith("_ref") and isinstance(value, str) and value:
            rels.append((source_id, value, key))
        elif key.endswith("_refs") and isinstance(value, list):
            for ref in value:
                if isinstance(ref, str) and ref:
                    rels.append((source_id, ref, key))
    return rels


def _flush_nodes(session, label: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    query = (
        "UNWIND $rows AS row "
        "MERGE (n:MHD {id: row.id}) "
        f"SET n:{label} "
        "SET n += row.props"
    )
    session.run(query, rows=rows)


def _flush_relationships(
    session,
    rel_type: str,
    rows: list[dict[str, Any]],
    has_id: bool,
) -> None:
    if not rows:
        return
    if has_id:
        query = (
            "UNWIND $rows AS row "
            "MATCH (a:MHD {id: row.source_id}) "
            "MATCH (b:MHD {id: row.target_id}) "
            f"MERGE (a)-[r:{rel_type} {{id: row.id}}]->(b) "
            "SET r += row.props"
        )
    else:
        query = (
            "UNWIND $rows AS row "
            "MATCH (a:MHD {id: row.source_id}) "
            "MATCH (b:MHD {id: row.target_id}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            "SET r += row.props"
        )
    session.run(query, rows=rows)


@click.command(name="load-neo4j")
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--pattern", default="*.mhd.json", show_default=True)
@click.option("--uri", default=None, help="Neo4j URI (env: NEO4J_URI)")
@click.option("--user", default=None, help="Neo4j user (env: NEO4J_USER)")
@click.option(
    "--password",
    default=None,
    help="Neo4j password (env: NEO4J_PASSWORD)",
    hide_input=True,
)
@click.option("--database", default=None, help="Neo4j database (env: NEO4J_DATABASE)")
@click.option("--batch-size", type=int, default=1000, show_default=True)
@click.option("--max-files", type=int, default=0, show_default=True)
@click.option(
    "--include-embedded/--skip-embedded",
    default=True,
    show_default=True,
)
@click.option("--ensure-constraint/--skip-constraint", default=True, show_default=True)
@click.option("--dry-run", is_flag=True, default=False)
def load_neo4j(
    input_dir: str,
    pattern: str,
    uri: str | None,
    user: str | None,
    password: str | None,
    database: str | None,
    batch_size: int,
    max_files: int,
    include_embedded: bool,
    ensure_constraint: bool,
    dry_run: bool,
) -> None:
    """Load MHD graph JSON files into Neo4j."""

    input_path = Path(input_dir)
    files = iter_input_files(input_path, pattern)
    if not files:
        raise click.ClickException(f"No files found in {input_path} matching {pattern}")
    if max_files and max_files > 0:
        files = files[:max_files]

    mhd_files: list[tuple[Path, dict[str, Any]]] = []
    errors: list[tuple[str, str]] = []
    for path in files:
        try:
            mhd_files.append((path, load_json_file(path)))
        except Exception as e:
            errors.append((str(path), str(e)))

    if errors:
        eprint(f"Failed to parse {len(errors)} file(s). Skipping them.")
        for fp, msg in errors:
            eprint(f"{fp}: {msg}")

    if not mhd_files:
        raise click.ClickException("No valid MHD files to process.")

    node_count = 0
    rel_count = 0
    embedded_count = 0

    if dry_run:
        for _, mhd in mhd_files:
            graph = mhd.get("graph", {})
            node_count += len(graph.get("nodes", []))
            rel_count += len(graph.get("relationships", []))
            if include_embedded:
                for node in graph.get("nodes", []):
                    embedded_count += len(_extract_embedded_relationships(node))
        eprint(
            f"Dry run: nodes={node_count} relationships={rel_count} embedded={embedded_count}"
        )
        return

    neo4j_uri = uri or os.getenv("NEO4J_URI") or "bolt://localhost:7687"
    neo4j_user = user or os.getenv("NEO4J_USER") or "neo4j"
    neo4j_password = password or os.getenv("NEO4J_PASSWORD")
    neo4j_database = database or os.getenv("NEO4J_DATABASE")

    if not neo4j_password:
        raise click.ClickException(
            "Neo4j password not provided. Use --password or NEO4J_PASSWORD."
        )

    driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
    try:
        with driver.session(database=neo4j_database) as session:
            if ensure_constraint:
                session.run(
                    "CREATE CONSTRAINT mhd_id IF NOT EXISTS "
                    "FOR (n:MHD) REQUIRE n.id IS UNIQUE"
                )

            node_batches: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for _, mhd in mhd_files:
                graph = mhd.get("graph", {})
                for node in graph.get("nodes", []):
                    node_id = node.get("id")
                    if not node_id:
                        continue
                    label = _sanitize_token(node.get("type"), prefix="T")
                    props = _coerce_props(node)
                    node_batches[label].append({"id": node_id, "props": props})
                    node_count += 1
                    if len(node_batches[label]) >= batch_size:
                        _flush_nodes(session, label, node_batches[label])
                        node_batches[label].clear()

            for label, rows in node_batches.items():
                _flush_nodes(session, label, rows)

            rel_batches: dict[tuple[str, bool], list[dict[str, Any]]] = defaultdict(
                list
            )
            for _, mhd in mhd_files:
                graph = mhd.get("graph", {})
                for rel in graph.get("relationships", []):
                    source_id = rel.get("source_ref")
                    target_id = rel.get("target_ref")
                    if not source_id or not target_id:
                        continue
                    rel_type = _sanitize_token(rel.get("relationship_name"), prefix="R")
                    props = {
                        k: v
                        for k, v in rel.items()
                        if k not in {"source_ref", "target_ref"}
                    }
                    props = _coerce_props(props)
                    rel_id = props.get("id")
                    key = (rel_type, bool(rel_id))
                    rel_batches[key].append(
                        {
                            "source_id": source_id,
                            "target_id": target_id,
                            "id": rel_id,
                            "props": props,
                        }
                    )
                    rel_count += 1
                    if len(rel_batches[key]) >= batch_size:
                        _flush_relationships(
                            session, rel_type, rel_batches[key], key[1]
                        )
                        rel_batches[key].clear()

                if include_embedded:
                    for node in graph.get("nodes", []):
                        for (
                            source_id,
                            target_id,
                            key_name,
                        ) in _extract_embedded_relationships(node):
                            rel_type = _sanitize_token(key_name, prefix="R")
                            key = (rel_type, False)
                            rel_batches[key].append(
                                {
                                    "source_id": source_id,
                                    "target_id": target_id,
                                    "id": None,
                                    "props": {},
                                }
                            )
                            embedded_count += 1
                            if len(rel_batches[key]) >= batch_size:
                                _flush_relationships(
                                    session, rel_type, rel_batches[key], False
                                )
                                rel_batches[key].clear()

            for (rel_type, has_id), rows in rel_batches.items():
                _flush_relationships(session, rel_type, rows, has_id)
    finally:
        driver.close()

    eprint(
        f"Loaded nodes={node_count} relationships={rel_count} embedded={embedded_count}"
    )
