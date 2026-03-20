from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel

from mhd_ws.domain.entities.search.index_search_spec import Target, ValueType
from mhd_ws.domain.entities.search.types import (
    ComparatorOp,
    IntraFieldCombiner,
    MatchMode,
)


# ---------------------------------------------------------------------------
# Field registry models
# ---------------------------------------------------------------------------


class AllowedOperators(BaseModel):
    allow_terms: bool = True
    allow_comparators: bool = False
    allowed_match_modes: list[MatchMode] = ["AUTO"]
    allowed_intra_combiners: list[IntraFieldCombiner] = ["AND", "OR"]
    allowed_comparators: list[ComparatorOp] = []


class FieldDef(BaseModel):
    field_id: str
    field_key: str
    target: Target
    value_type: ValueType
    ops: AllowedOperators
    description: str = ""
    facet_key: Optional[str] = None
    facet_type: Optional[Literal["value", "range", "date_histogram"]] = None


class FieldRegistry(BaseModel):
    fields: list[FieldDef]

    def get_by_id(self, field_id: str) -> FieldDef | None:
        for f in self.fields:
            if f.field_id == field_id:
                return f
        return None

    def get_by_id_strict(self, field_id: str) -> FieldDef:
        result = self.get_by_id(field_id)
        if result is None:
            raise ValueError(f"Unknown field_id: {field_id!r}")
        return result


# ---------------------------------------------------------------------------
# Index capability models
# ---------------------------------------------------------------------------


class TextQueryStrategy(str, Enum):
    MATCH = "MATCH"


class KeywordQueryStrategy(str, Enum):
    TERMS = "TERMS"


class NestedSpec(BaseModel):
    path: str


class FieldCapability(BaseModel):
    field_key: str
    value_type: ValueType
    es_path: str
    nested: Optional[NestedSpec] = None
    supports_terms: bool = True
    supports_phrase: bool = False
    supports_exact: bool = False
    supports_comparators: bool = False
    text_strategy: Optional[TextQueryStrategy] = None
    keyword_strategy: Optional[KeywordQueryStrategy] = None
    exact_es_path: Optional[str] = None


class JoinContract(BaseModel):
    dataset_id_field_key: str


class IndexCapabilities(BaseModel):
    index_key: str
    concrete_index_or_alias: str
    api_key_name: Optional[str] = None
    join: JoinContract
    fields: list[FieldCapability]

    def get_field(self, field_key: str) -> FieldCapability | None:
        for f in self.fields:
            if f.field_key == field_key:
                return f
        return None

    def get_field_strict(self, field_key: str) -> FieldCapability:
        result = self.get_field(field_key)
        if result is None:
            raise ValueError(
                f"Field {field_key!r} not found in index {self.index_key!r}"
            )
        return result


class IndexCapabilitiesRegistry(BaseModel):
    indices: list[IndexCapabilities]

    def get_index(self, index_key: str) -> IndexCapabilities | None:
        for idx in self.indices:
            if idx.index_key == index_key:
                return idx
        return None

    def get_index_strict(self, index_key: str) -> IndexCapabilities:
        result = self.get_index(index_key)
        if result is None:
            raise ValueError(f"Unknown index_key: {index_key!r}")
        return result
