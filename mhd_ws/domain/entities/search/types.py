"""Compatibility re-export for advanced-search core types.

Prefer importing from ``mhd_ws.domain.entities.search.advanced_core`` for any
new advanced-search code. This module remains only to avoid a flag-day import
rewrite while the extraction boundary settles.
"""

from mhd_ws.domain.entities.search.advanced_core.types import (
    ComparatorOp,
    InterFieldCombiner,
    IntraFieldCombiner,
    MatchMode,
)

__all__ = [
    "ComparatorOp",
    "InterFieldCombiner",
    "IntraFieldCombiner",
    "MatchMode",
]
