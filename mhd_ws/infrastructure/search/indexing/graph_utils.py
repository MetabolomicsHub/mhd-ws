"""Graph helpers for MHD datasets."""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from typing import Any


@dataclasses.dataclass
class RelIndex:
    out_by_src: dict[tuple[str, str], list[str]]
    out_by_tgt: dict[tuple[str, str], list[str]]


def build_rel_index(relationships: list[dict[str, Any]]) -> RelIndex:
    """Build relationship lookup maps keyed by (node_id, relationship_name)."""
    out_by_src: dict[tuple[str, str], list[str]] = defaultdict(list)
    out_by_tgt: dict[tuple[str, str], list[str]] = defaultdict(list)
    for r in relationships:
        if r.get("type") != "relationship":
            continue
        s = r.get("source_ref")
        t = r.get("target_ref")
        name = r.get("relationship_name")
        if not s or not t or not name:
            continue
        out_by_src[(s, name)].append(t)
        out_by_tgt[(t, name)].append(s)
    return RelIndex(out_by_src=out_by_src, out_by_tgt=out_by_tgt)


def rel_targets(relidx: RelIndex, source_id: str, rel_name: str) -> list[str]:
    """Return target ids for a given source id and relationship name."""
    return relidx.out_by_src.get((source_id, rel_name), [])


def rel_sources(relidx: RelIndex, target_id: str, rel_name: str) -> list[str]:
    """Return source ids for a given target id and relationship name."""
    return relidx.out_by_tgt.get((target_id, rel_name), [])


def get_graph_parts(
    mhd: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Return node lookup and relationship list from an MHD graph."""
    graph = mhd.get("graph") or {}
    nodes = graph.get("nodes") or []
    relationships = graph.get("relationships")
    if relationships is None:
        relationships = [n for n in nodes if n.get("type") == "relationship"]
    else:
        relationships = list(relationships)
    node_by_id = {n["id"]: n for n in nodes if n.get("id")}
    return node_by_id, relationships


def choose_study_id(mhd: dict[str, Any], node_by_id: dict[str, dict[str, Any]]) -> str:
    """Select the study node id using start refs or fallback to first study."""
    graph = mhd.get("graph") or {}
    start_refs = graph.get("start_item_refs") or []
    for ref in start_refs:
        n = node_by_id.get(ref)
        if n and n.get("type") == "study":
            return ref
    for nid, n in node_by_id.items():
        if n.get("type") == "study":
            return nid
    raise ValueError("no study node found")


def node_name(node: dict[str, Any] | None) -> str | None:
    """Return a best-effort display name for a node."""
    if not node:
        return None
    for k in ("name", "title", "full_name", "label"):
        v = node.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def cv_value_label_and_accession(
    cv: dict[str, Any],
) -> tuple[str | None, str | None]:
    """Extract a label and accession from a characteristic-value-like node."""
    accession = cv.get("accession")
    label = cv.get("label") or cv.get("name") or accession
    if isinstance(label, str):
        label = label.strip()
    if isinstance(accession, str):
        accession = accession.strip()
    return (label or None), (accession or None)
