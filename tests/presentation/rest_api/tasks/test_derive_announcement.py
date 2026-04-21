"""Tests for derive_announcement() core function."""

from __future__ import annotations

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

FAKE_ANNOUNCEMENT = {"mhd_identifier": "MHD000001", "profile_uri": "ms-profile.json"}
FAKE_ANNOUNCEMENT_STR = json.dumps(FAKE_ANNOUNCEMENT)
FAKE_SHA256 = hashlib.sha256(FAKE_ANNOUNCEMENT_STR.encode()).hexdigest()
FAKE_MHD_JSON = {"mhd_identifier": "MHD000001", "title": "Test"}


def _make_dataset(
    accession="MHD000001", accession_type="mhd", dataset_id=1, revision=0
):
    ds = MagicMock()
    ds.id = dataset_id
    ds.accession = accession
    ds.accession_type = accession_type
    ds.revision = revision
    ds.repository_id = 99
    return ds


class TestDeriveAnnouncement:
    @pytest.mark.asyncio
    async def test_happy_path_stores_new_revision(self):
        """Happy path: mhd_file provided, converts and stores new revision."""
        from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.tasks import (
            derive_announcement,
        )

        db_client = MagicMock()
        session = AsyncMock()
        db_client.session.return_value.__aenter__ = AsyncMock(return_value=session)
        db_client.session.return_value.__aexit__ = AsyncMock(return_value=False)
        cache_service = AsyncMock()
        cache_service.delete_key = AsyncMock(return_value=True)
        dataset = _make_dataset(revision=0)

        session.execute = AsyncMock(
            side_effect=[
                MagicMock(
                    scalar_one_or_none=MagicMock(return_value=dataset)
                ),  # profile lookup
                MagicMock(
                    scalar_one_or_none=MagicMock(return_value=dataset)
                ),  # locked lookup
                MagicMock(scalar=MagicMock(return_value=None)),  # max revision = None
            ]
        )
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        with (
            patch(
                "mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.tasks.convert_mhd_to_announcement",
                return_value=FAKE_ANNOUNCEMENT,
            ),
            patch(
                "mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.tasks.ProfileEnabledDataset"
            ) as mock_pe,
            patch(
                "mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.tasks.SUPPORTED_SCHEMA_MAP"
            ) as mock_schema_map,
        ):
            mock_pe.model_validate.return_value = MagicMock(
                schema_name="schema-v1", profile_uri="ms-profile.json"
            )
            mock_schema_map.schemas = {}
            mock_schema_map.default_schema_uri = "default"

            result = await derive_announcement(
                accession="MHD000001",
                mhd_file_url="https://example.com/MHD000001.mhd.json",
                mhd_file=FAKE_MHD_JSON,
                database_client=db_client,
                cache_service=cache_service,
            )

        assert result["success"] is True
        session.add.assert_called()
        session.commit.assert_called_once()
        cache_service.delete_key.assert_called_once_with(
            "announcement-file:MHD000001:latest"
        )

    @pytest.mark.asyncio
    async def test_skips_cache_invalidation_when_cache_service_is_none(self):
        """When cache_service=None (e.g. CLI), storage succeeds without cache invalidation."""
        from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.tasks import (
            derive_announcement,
        )

        db_client = MagicMock()
        session = AsyncMock()
        db_client.session.return_value.__aenter__ = AsyncMock(return_value=session)
        db_client.session.return_value.__aexit__ = AsyncMock(return_value=False)
        dataset = _make_dataset(revision=0)

        session.execute = AsyncMock(
            side_effect=[
                MagicMock(scalar_one_or_none=MagicMock(return_value=dataset)),
                MagicMock(scalar_one_or_none=MagicMock(return_value=dataset)),
                MagicMock(scalar=MagicMock(return_value=None)),
            ]
        )
        session.add = MagicMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()

        with (
            patch(
                "mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.tasks.convert_mhd_to_announcement",
                return_value=FAKE_ANNOUNCEMENT,
            ),
            patch(
                "mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.tasks.ProfileEnabledDataset"
            ) as mock_pe,
            patch(
                "mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.tasks.SUPPORTED_SCHEMA_MAP"
            ) as mock_schema_map,
        ):
            mock_pe.model_validate.return_value = MagicMock(
                schema_name="schema-v1", profile_uri="ms-profile.json"
            )
            mock_schema_map.schemas = {}
            mock_schema_map.default_schema_uri = "default"

            result = await derive_announcement(
                accession="MHD000001",
                mhd_file_url="https://example.com/MHD000001.mhd.json",
                mhd_file=FAKE_MHD_JSON,
                database_client=db_client,
                cache_service=None,
            )

        assert result["success"] is True
        session.add.assert_called()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_if_sha256_unchanged(self):
        """If sha256 matches current revision, returns unchanged message."""
        from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.tasks import (
            derive_announcement,
        )

        db_client = MagicMock()
        session = AsyncMock()
        db_client.session.return_value.__aenter__ = AsyncMock(return_value=session)
        db_client.session.return_value.__aexit__ = AsyncMock(return_value=False)
        cache_service = AsyncMock()
        dataset = _make_dataset(revision=1)
        latest_revision = MagicMock()
        latest_revision.file_id = 42

        session.execute = AsyncMock(
            side_effect=[
                MagicMock(
                    scalar_one_or_none=MagicMock(return_value=dataset)
                ),  # profile lookup
                MagicMock(scalar_one_or_none=MagicMock(return_value=dataset)),  # locked
                MagicMock(
                    scalar_one_or_none=MagicMock(return_value=latest_revision)
                ),  # latest revision
                MagicMock(scalar=MagicMock(return_value=FAKE_SHA256)),  # same sha256
            ]
        )
        session.add = MagicMock()

        with patch(
            "mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.tasks.convert_mhd_to_announcement",
            return_value=FAKE_ANNOUNCEMENT,
        ):
            result = await derive_announcement(
                accession="MHD000001",
                mhd_file_url="https://example.com/MHD000001.mhd.json",
                mhd_file=FAKE_MHD_JSON,
                database_client=db_client,
                cache_service=cache_service,
            )

        assert result["success"] is False
        assert "unchanged" in result["message"].lower()
        session.add.assert_not_called()
        cache_service.delete_key.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_error_if_dataset_not_found(self):
        """Returns error dict when accession not in DB."""
        from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.tasks import (
            derive_announcement,
        )

        db_client = MagicMock()
        session = AsyncMock()
        db_client.session.return_value.__aenter__ = AsyncMock(return_value=session)
        db_client.session.return_value.__aexit__ = AsyncMock(return_value=False)

        session.execute = AsyncMock(
            return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
        )

        result = await derive_announcement(
            accession="MHD999999",
            mhd_file_url="https://example.com/MHD999999.mhd.json",
            mhd_file=FAKE_MHD_JSON,
            database_client=db_client,
            cache_service=None,
        )

        assert result["success"] is False
        assert "not found" in result["message"].lower()
