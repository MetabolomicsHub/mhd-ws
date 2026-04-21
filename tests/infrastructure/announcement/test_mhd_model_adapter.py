"""Tests for the mhd-model announcement converter shim."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from mhd_ws.application.use_cases.announcement_conversion import (
    convert_mhd_to_announcement,
)

FAKE_ANNOUNCEMENT = {"mhd_identifier": "MHD000001", "title": "Test Dataset"}


def _make_fake_create(fake_data):
    """Side effect that writes fake announcement JSON to the temp path."""

    def fake_create(mhd_file, mhd_file_url, announcement_file_path, **kwargs):
        with Path(announcement_file_path).open("w") as f:
            json.dump(fake_data, f)

    return fake_create


class TestConvertMhdToAnnouncement:
    def test_returns_dict_for_ms_profile(self):
        mhd_file = {"profile": "ms", "data": "fake"}
        mhd_file_url = "https://example.com/dataset.mhd.json"

        with patch(
            "mhd_ws.application.use_cases.announcement_conversion.ms_create_announcement_file"
        ) as mock_ms:
            mock_ms.side_effect = _make_fake_create(FAKE_ANNOUNCEMENT)
            result = convert_mhd_to_announcement(mhd_file, mhd_file_url, profile="ms")

        assert result == FAKE_ANNOUNCEMENT
        mock_ms.assert_called_once()
        call_kwargs = mock_ms.call_args.kwargs
        assert call_kwargs["mhd_file"] == mhd_file
        assert call_kwargs["mhd_file_url"] == mhd_file_url

    def test_returns_dict_for_legacy_profile(self):
        mhd_file = {"profile": "legacy", "data": "fake"}
        mhd_file_url = "https://example.com/legacy.mhd.json"

        with patch(
            "mhd_ws.application.use_cases.announcement_conversion.legacy_create_announcement_file"
        ) as mock_legacy:
            mock_legacy.side_effect = _make_fake_create(FAKE_ANNOUNCEMENT)
            result = convert_mhd_to_announcement(
                mhd_file, mhd_file_url, profile="legacy"
            )

        assert result == FAKE_ANNOUNCEMENT
        mock_legacy.assert_called_once()
        call_kwargs = mock_legacy.call_args.kwargs
        assert call_kwargs["mhd_file"] == mhd_file
        assert call_kwargs["mhd_file_url"] == mhd_file_url

    def test_raises_for_unknown_profile(self):
        with pytest.raises(ValueError, match="Unknown profile"):
            convert_mhd_to_announcement({}, "https://x.com", profile="unknown")

    def test_raises_if_converter_raises(self):
        """If the converter raises, the error propagates."""
        with patch(
            "mhd_ws.application.use_cases.announcement_conversion.ms_create_announcement_file"
        ) as mock_ms:
            mock_ms.side_effect = RuntimeError("converter failed")
            with pytest.raises(RuntimeError, match="converter failed"):
                convert_mhd_to_announcement({}, "https://x.com", profile="ms")
