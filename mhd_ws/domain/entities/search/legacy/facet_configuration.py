from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class FacetConfig:
    field: str
    type: Literal["value", "range"] = "value"


@dataclass(frozen=True)
class RangeFacetConfig(FacetConfig):
    type: Literal["value", "range"] = "range"
    interval: str = "year"

    def build_ranges(self) -> list[dict]:
        current_year = datetime.now().year
        ranges: list[dict] = []
        for year in range(current_year, current_year - 20, -1):
            ranges.append(
                {
                    "from": f"{year}-01-01",
                    "to": f"{year + 1}-01-01",
                    "key": str(year),
                }
            )
        ranges.append({"to": f"{current_year - 19}-01-01", "key": f"Before {current_year - 19}"})
        return ranges


_VALUE_FACET_FIELDS = [
    "organisms",
    "diseases",
    "tissues",
    "sample_types",
    "characteristic_types",
    "omics_types",
    "measurement_types",
    "assay_types",
    "technology_types",
]

LEGACY_FACET_CONFIG: dict[str, FacetConfig] = {}

for _name in _VALUE_FACET_FIELDS:
    LEGACY_FACET_CONFIG[_name] = FacetConfig(field=f"facets.{_name}", type="value")

LEGACY_FACET_CONFIG["profile"] = FacetConfig(field="profile", type="value")

LEGACY_FACET_CONFIG["submission_date"] = RangeFacetConfig(
    field="dates.submission", type="range", interval="year"
)
LEGACY_FACET_CONFIG["public_release_date"] = RangeFacetConfig(
    field="dates.public_release", type="range", interval="year"
)
