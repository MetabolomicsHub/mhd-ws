"""Tests for CLI announcement loading accession parsing."""
from __future__ import annotations

from pathlib import Path

from mhd_ws.run.cli.announcement.load_announcement import (
    _get_accession,
    _get_announcement_files,
)


class TestGetAccession:
    def test_uses_filename_stem_without_announcement_suffix(self):
        accession = _get_accession({}, Path("MSV000101216.announcement.json"))
        assert accession == "MSV000101216"

    def test_uses_filename_stem_without_mhd_suffix(self):
        accession = _get_accession({}, Path("MSV000101216.mhd.json"))
        assert accession == "MSV000101216"

    def test_strips_md_suffix_from_identifier(self):
        accession = _get_accession(
            {"mhd_identifier": "MSV000101216.announcement.md"},
            Path("ignored.json"),
        )
        assert accession == "MSV000101216"


class TestGetAnnouncementFiles:
    def test_skips_mhd_json_files(self, tmp_path):
        (tmp_path / "MSV000101216.announcement.json").write_text("{}", encoding="utf-8")
        (tmp_path / "MSV000101216.mhd.json").write_text("{}", encoding="utf-8")
        (tmp_path / "other.json").write_text("{}", encoding="utf-8")

        files = _get_announcement_files(tmp_path)

        assert [path.name for path in files] == [
            "MSV000101216.announcement.json",
            "other.json",
        ]
