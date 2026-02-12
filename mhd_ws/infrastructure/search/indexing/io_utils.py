"""File IO helpers for output formats."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


def iter_input_files(input_dir: Path, pattern: str) -> list[Path]:
    """Return sorted, existing files matching the glob pattern."""
    files = sorted(input_dir.glob(pattern))
    return [p for p in files if p.is_file()]


def write_bulk(
    out_fh,
    docs: Iterable[dict[str, Any]],
    index_name: str,
    op_type: str,
) -> int:
    """Write Elasticsearch Bulk API NDJSON for the given documents."""
    n = 0
    for doc in docs:
        doc_id = doc.get("id")
        meta = {op_type: {"_index": index_name}}
        if doc_id:
            meta[op_type]["_id"] = doc_id
        out_fh.write(json.dumps(meta, ensure_ascii=False) + "\n")
        out_fh.write(json.dumps(doc, ensure_ascii=False) + "\n")
        n += 1
    return n


def write_jsonl(out_fh, docs: Iterable[dict[str, Any]]) -> int:
    """Write one JSON document per line (NDJSON docs only)."""
    n = 0
    for doc in docs:
        out_fh.write(json.dumps(doc, ensure_ascii=False) + "\n")
        n += 1
    return n


def write_json_dir(out_dir: Path, docs: Iterable[dict[str, Any]]) -> int:
    """Write one pretty-printed JSON file per document."""
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for doc in docs:
        doc_id = doc.get("id") or f"doc_{n}"
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", doc_id)
        path = out_dir / f"{safe}.json"
        path.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        n += 1
    return n
