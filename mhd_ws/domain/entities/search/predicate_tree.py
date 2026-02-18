from datetime import date, datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from mhd_ws.domain.entities.search.types import ComparatorOp


PredicateKind = Literal["TERM_MATCH", "PHRASE_MATCH", "EXACT_MATCH", "RANGE"]


class AndExpr(BaseModel):
    kind: Literal["AND"] = "AND"
    children: list["BoolExpr"]


class OrExpr(BaseModel):
    kind: Literal["OR"] = "OR"
    children: list["BoolExpr"]


class NotExpr(BaseModel):
    kind: Literal["NOT"] = "NOT"
    child: "BoolExpr"


class TermMatchPredicate(BaseModel):
    kind: Literal["TERM_MATCH"] = "TERM_MATCH"
    field_key: str
    value: str


class PhraseMatchPredicate(BaseModel):
    kind: Literal["PHRASE_MATCH"] = "PHRASE_MATCH"
    field_key: str
    value: str


class ExactMatchPredicate(BaseModel):
    kind: Literal["EXACT_MATCH"] = "EXACT_MATCH"
    field_key: str
    value: str


class RangePredicate(BaseModel):
    kind: Literal["RANGE"] = "RANGE"
    field_key: str
    op: ComparatorOp
    value: Union[str, int, float, date, datetime]


Predicate = Annotated[
    Union[TermMatchPredicate, PhraseMatchPredicate, ExactMatchPredicate, RangePredicate],
    Field(discriminator="kind"),
]

BoolExpr = Annotated[
    Union[AndExpr, OrExpr, NotExpr, Predicate],
    Field(discriminator="kind"),
]

AndExpr.model_rebuild()
OrExpr.model_rebuild()
NotExpr.model_rebuild()
