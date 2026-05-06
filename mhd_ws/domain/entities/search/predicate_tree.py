"""Compatibility re-export for advanced-search predicate models.

Prefer importing from ``mhd_ws.domain.entities.search.advanced_core`` for any
new advanced-search code. This shim exists to keep legacy imports stable while
the shared-core boundary is being extracted.
"""

from mhd_ws.domain.entities.search.advanced_core.predicates import (
    AndExpr,
    BoolExpr,
    CharacteristicPairPredicate,
    DescriptorPredicate,
    ExactMatchPredicate,
    NotExpr,
    OrExpr,
    ParameterPairPredicate,
    PhraseMatchPredicate,
    Predicate,
    PredicateKind,
    RangePredicate,
    TermMatchPredicate,
)

__all__ = [
    "AndExpr",
    "BoolExpr",
    "CharacteristicPairPredicate",
    "DescriptorPredicate",
    "ExactMatchPredicate",
    "NotExpr",
    "OrExpr",
    "ParameterPairPredicate",
    "PhraseMatchPredicate",
    "Predicate",
    "PredicateKind",
    "RangePredicate",
    "TermMatchPredicate",
]
