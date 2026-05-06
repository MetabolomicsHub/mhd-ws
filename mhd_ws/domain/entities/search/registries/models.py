"""Compatibility re-export for advanced-search registry model classes.

Prefer importing from ``mhd_ws.domain.entities.search.advanced_core`` for any
new advanced-search code. Registry instances still stay local to ``mhd-ws``;
only the shared model classes are being prepared for extraction.
"""

from mhd_ws.domain.entities.search.advanced_core.registries import (
    AllowedOperators,
    FieldCapability,
    FieldDef,
    FieldRegistry,
    IndexCapabilities,
    IndexCapabilitiesRegistry,
    JoinContract,
    KeywordQueryStrategy,
    NestedSpec,
    TextQueryStrategy,
)

__all__ = [
    "AllowedOperators",
    "FieldCapability",
    "FieldDef",
    "FieldRegistry",
    "IndexCapabilities",
    "IndexCapabilitiesRegistry",
    "JoinContract",
    "KeywordQueryStrategy",
    "NestedSpec",
    "TextQueryStrategy",
]
