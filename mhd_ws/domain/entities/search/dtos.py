from __future__ import annotations

from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field

from mhd_ws.domain.entities.search.types import (
    ComparatorOp,
    InterFieldCombiner,
    IntraFieldCombiner,
    MatchMode,
)


class TermClauseDTO(BaseModel):
    kind: Literal["terms"] = "terms"
    field_id: str
    op: IntraFieldCombiner
    not_: bool = Field(default=False, alias="not")
    terms: Annotated[list[str], Field(min_length=1)]
    match: MatchMode = "AUTO"


class ComparatorClauseDTO(BaseModel):
    kind: Literal["compare"] = "compare"
    field_id: str
    op: ComparatorOp
    not_: bool = Field(default=False, alias="not")
    value: Union[str, int, float]


class ParameterPairClauseDTO(BaseModel):
    kind: Literal["parameter_pair"] = "parameter_pair"
    type_name: str
    values: list[str]
    op: IntraFieldCombiner = "OR"
    not_: bool = Field(default=False, alias="not")
    include_facet: bool = False


FieldClauseDTO = Annotated[
    Union[TermClauseDTO, ComparatorClauseDTO, ParameterPairClauseDTO],
    Field(discriminator="kind"),
]


class PageDTO(BaseModel):
    current: int = Field(ge=1)
    size: int = Field(ge=1, le=10_000)


class SortDTO(BaseModel):
    field: str
    direction: Literal["asc", "desc"]


class SearchRequestDTO(BaseModel):
    version: Literal["v1"] = "v1"
    query_text: Optional[str] = None
    inter_field_combiner: InterFieldCombiner = "AND"
    clauses: list[FieldClauseDTO] = Field(default_factory=list)
    page: Optional[PageDTO] = None
    sort: list[SortDTO] = Field(default_factory=list)
