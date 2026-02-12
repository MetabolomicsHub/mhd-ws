from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from mhd_ws.domain.shared.model import MhdBaseModel


class PageModel(MhdBaseModel):
    current: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=200)


class SortModel(MhdBaseModel):
    field: str
    direction: Literal["asc", "desc"] = "asc"


class FilterModel(MhdBaseModel):
    field: str
    values: list[str]
    operator: Literal["all", "any", "none"] = "any"


class FacetBucket(MhdBaseModel):
    value: str
    count: int


class FacetResponse(MhdBaseModel):
    type: Literal["value", "range"] = "value"
    data: list[FacetBucket] = Field(default_factory=list)


class IndexSearchResult(MhdBaseModel):
    results: list[dict[str, Any]] = Field(default_factory=list)
    total_results: int = 0
    facets: dict[str, FacetResponse] = Field(default_factory=dict)
    request_id: str = ""
