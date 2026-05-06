"""Compatibility re-export for advanced-search plan/stage models.

Prefer importing from ``mhd_ws.domain.entities.search.advanced_core`` for any
new advanced-search code. This module remains as a transitional import shim.
"""

from mhd_ws.domain.entities.search.advanced_core.plan import (
    DatasetHitsOutput,
    DatasetIdConstraint,
    DatasetIdSetOutput,
    DatasetSearchStage,
    MetaboliteIdStage,
    QueryPlan,
    QueryStage,
)

__all__ = [
    "DatasetHitsOutput",
    "DatasetIdConstraint",
    "DatasetIdSetOutput",
    "DatasetSearchStage",
    "MetaboliteIdStage",
    "QueryPlan",
    "QueryStage",
]
