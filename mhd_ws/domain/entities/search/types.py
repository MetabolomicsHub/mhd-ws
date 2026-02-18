from __future__ import annotations

from typing import Literal

InterFieldCombiner = Literal["AND", "OR"]
IntraFieldCombiner = Literal["AND", "OR"]
MatchMode = Literal["AUTO", "EXACT", "PHRASE"]

ComparatorOp = Literal["GT", "GTE", "LT", "LTE", "EQ"]
