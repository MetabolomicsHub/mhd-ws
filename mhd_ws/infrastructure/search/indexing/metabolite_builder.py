"""Build metabolite annotation documents."""

from __future__ import annotations

from typing import Any

from mhd_ws.infrastructure.search.indexing.graph_utils import (
    build_rel_index,
    choose_study_id,
    get_graph_parts,
    rel_sources,
)


def build_metabolite_docs(
    mhd: dict[str, Any], dataset_doc: dict[str, Any]
) -> list[dict[str, Any]]:
    """Build metabolite documents for a dataset."""
    node_by_id, relationships = get_graph_parts(mhd)
    relidx = build_rel_index(relationships)
    study_id = choose_study_id(mhd, node_by_id)
    study = node_by_id.get(study_id, {})

    dataset_id = dataset_doc.get("id")
    repo = dataset_doc.get("repository", {})

    docs: list[dict[str, Any]] = []
    for m in node_by_id.values():
        if m.get("type") != "metabolite":
            continue
        metabolite_id = m.get("id")
        if not metabolite_id:
            continue

        identifier_nodes: list[dict[str, Any]] = []
        identifiers: list[dict[str, Any]] = []
        seen: set[tuple[str, ...]] = set()
        for rel_name in ("reported-identifier-of", "identifier-of"):
            for ident_id in rel_sources(relidx, metabolite_id, rel_name):
                ident = node_by_id.get(ident_id)
                if not isinstance(ident, dict):
                    continue
                identifier_nodes.append(ident)
                entry = {
                    "source": ident.get("source"),
                    "accession": ident.get("accession"),
                    "name": ident.get("name"),
                    "type": ident.get("type"),
                }
                key = (
                    (entry.get("source") or "").strip(),
                    (entry.get("accession") or "").strip(),
                    (entry.get("name") or "").strip(),
                    (entry.get("type") or "").strip(),
                )
                if key in seen:
                    continue
                seen.add(key)
                identifiers.append(entry)

        metabolite_doc: dict[str, Any] = {
            "id": f"{dataset_id}::metabolite::{metabolite_id}",
            "dataset_id": dataset_id,
            "profile": dataset_doc.get("profile"),
            "repository": repo,
            "study": {"title": study.get("title")},
            "metabolite": {
                "node_id": metabolite_id,
                "name": m.get("name"),
                "accession": m.get("accession"),
                "source": m.get("source"),
                "identifiers": identifiers,
            },
            "raw": {"metabolite": m, "identifiers": identifier_nodes},
        }
        docs.append(metabolite_doc)

    return docs
