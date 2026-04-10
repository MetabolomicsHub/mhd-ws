"""Generic helper utilities."""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

MERGE_CONFLICT_RE = re.compile(r"^(<<<<<<<|=======|>>>>>>>)", re.MULTILINE)
TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str | None) -> str:
    """Remove basic HTML tags and normalize whitespace."""
    if not text:
        return ""
    return TAG_RE.sub(" ", text).replace("\n", " ").replace("\r", " ").strip()


def dedup_preserve_order(values: Iterable[str]) -> list[str]:
    """Return unique, non-empty strings in their first-seen order."""
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        v2 = (v or "").strip()
        if not v2 or v2 in seen:
            continue
        seen.add(v2)
        out.append(v2)
    return out


def dedup_sorted_strings(values: Iterable[Any]) -> list[str]:
    """Return unique, non-empty strings sorted ascending."""
    return sorted({v.strip() for v in values if isinstance(v, str) and v.strip()})


def iso_now() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return dt.datetime.now(dt.timezone.utc).isoformat()


def load_json_file(path: Path) -> dict[str, Any]:
    """Load a JSON file, rejecting merge-conflict markers."""
    text = path.read_text(encoding="utf-8", errors="replace")
    if MERGE_CONFLICT_RE.search(text):
        raise ValueError(
            "merge-conflict markers detected (<<<<<<< / ======= / >>>>>>>)"
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON: {e}") from e


def eprint(*args: Any, **kwargs: Any) -> None:
    """Print to stderr."""
    sep = kwargs.pop("sep", " ")
    end = kwargs.pop("end", "\n")
    sys.stderr.write(sep.join(str(arg) for arg in args) + end)
    sys.stderr.flush()
