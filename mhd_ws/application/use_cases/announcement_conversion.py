"""Convert mhd.json payloads to announcement file payloads."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from mhd_model.convertors.announcement.convertor import create_announcement_file

_VALID_PROFILES = ("ms", "legacy")


def convert_mhd_to_announcement(
    mhd_file: dict[str, Any], mhd_file_url: str
) -> dict[str, Any]:
    """Convert an mhd.json dict to an announcement file dict."""

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "announcement.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        create_announcement_file(
            mhd_file=mhd_file,
            mhd_file_url=mhd_file_url,
            announcement_file_path=out_path,
        )
        with out_path.open() as f:
            return json.load(f)
