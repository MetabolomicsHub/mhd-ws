from datetime import date, datetime
from enum import Enum
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

from mhd_ws.domain.entities.search.types import (
    ComparatorOp,
    InterFieldCombiner,
    IntraFieldCombiner,
    MatchMode,
)


class Target(str, Enum):
    DATASET = "DATASET"
    METABOLITE = "METABOLITE"


class ValueType(str, Enum):
    TEXT = "TEXT"
    KEYWORD = "KEYWORD"
    NUMBER = "NUMBER"
    DATE = "DATE"


class FieldRef(BaseModel):
    field_key: str              # canonical stable identifier
    target: Target              # STUDY vs METABOLITE
    value_type: ValueType


class TermClauseSpec(BaseModel):
    kind: Literal["terms"] = "terms"
    field: FieldRef
    combine_within_field: IntraFieldCombiner
    negated: bool = False
    terms: Annotated[list[str], Field(min_length=1)]
    match: MatchMode = "AUTO"


class ComparatorClauseSpec(BaseModel):
    kind: Literal["compare"] = "compare"
    field: FieldRef
    comparator: ComparatorOp
    negated: bool = False
    value: Union[str, int, float, date, datetime]


FieldClauseSpec = Annotated[
    Union[TermClauseSpec, ComparatorClauseSpec],
    Field(discriminator="kind"),
]


class SearchSpec(BaseModel):
    query_text: Optional[str] = None
    inter_field_combiner: InterFieldCombiner = "AND"
    clauses: list[FieldClauseSpec] = Field(default_factory=list)
