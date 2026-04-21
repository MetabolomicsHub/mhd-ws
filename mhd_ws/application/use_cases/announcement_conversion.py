"""Convert mhd.json payloads to announcement file payloads."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from mhd_model.convertors.announcement.v0_1.legacy import (
    mhd2announce as legacy_mhd2announce,
)
from mhd_model.convertors.announcement.v0_1.ms import mhd2announce as ms_mhd2announce

_VALID_PROFILES = ("ms", "legacy")


def _resolve_converter(module: Any, *names: str) -> Any:
    for name in names:
        converter = getattr(module, name, None)
        if converter is not None:
            return converter

    raise ImportError(
        f"Could not find any of {names!r} in converter module {module.__name__!r}"
    )


ms_create_announcement_file = _resolve_converter(
    ms_mhd2announce,
    "create_announcement_file",
    "create_ms_announcement_file",
)
legacy_create_announcement_file = _resolve_converter(
    legacy_mhd2announce,
    "create_announcement_file",
    "create_legacy_announcement_file",
)


def convert_mhd_to_announcement(
    mhd_file: dict[str, Any],
    mhd_file_url: str,
    profile: str = "ms",
) -> dict[str, Any]:
    """Convert an mhd.json dict to an announcement file dict."""
    if profile == "ms":
        converter = ms_create_announcement_file
    elif profile == "legacy":
        converter = legacy_create_announcement_file
    else:
        raise ValueError(
            f"Unknown profile {profile!r}. Expected one of: {list(_VALID_PROFILES)}"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "announcement.json"
        converter(
            mhd_file=mhd_file,
            mhd_file_url=mhd_file_url,
            announcement_file_path=str(out_path),
        )
        with out_path.open() as f:
            return json.load(f)
