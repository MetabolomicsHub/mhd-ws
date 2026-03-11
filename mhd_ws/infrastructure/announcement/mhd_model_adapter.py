"""Shim adapter wrapping mhd-model converters to return dicts instead of writing files."""
from __future__ import annotations

import json
import os
import tempfile
from typing import Any

from mhd_model.convertors.announcement.v0_1.legacy.mhd2announce import (
    create_announcement_file as legacy_create_announcement_file,
)
from mhd_model.convertors.announcement.v0_1.ms.mhd2announce import (
    create_announcement_file as ms_create_announcement_file,
)

_VALID_PROFILES = ("ms", "legacy")


def convert_mhd_to_announcement(
    mhd_file: dict[str, Any],
    mhd_file_url: str,
    profile: str = "ms",
) -> dict[str, Any]:
    """Convert an mhd.json dict to an announcement file dict.

    Uses a temporary directory so the mhd-model converter can write to disk,
    then reads the result back. The temp dir is cleaned up automatically.

    Args:
        mhd_file: Parsed mhd.json as a dict.
        mhd_file_url: The URL where the mhd.json is publicly accessible.
                      This gets embedded in the announcement as mhd_metadata_file_url.
        profile: "ms" (default) or "legacy".

    Returns:
        Announcement file contents as a dict (JSON-serialisable).

    Raises:
        ValueError: If profile is not "ms" or "legacy".
        Any exception raised by the underlying converter.
    """
    if profile == "ms":
        converter = ms_create_announcement_file
    elif profile == "legacy":
        converter = legacy_create_announcement_file
    else:
        raise ValueError(
            f"Unknown profile {profile!r}. Expected one of: {list(_VALID_PROFILES)}"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, "announcement.json")
        converter(
            mhd_file=mhd_file,
            mhd_file_url=mhd_file_url,
            announcement_file_path=out_path,
        )
        with open(out_path) as f:
            return json.load(f)
