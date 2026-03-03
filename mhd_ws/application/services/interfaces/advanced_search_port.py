from __future__ import annotations

import abc
from typing import Any

from mhd_ws.domain.entities.search.index_search import (
    IndexSearchResult,
    PageModel,
    SortModel,
)
from mhd_ws.domain.entities.search.index_search_spec import SearchSpec


class AdvancedSearchPort(abc.ABC):
    @abc.abstractmethod
    async def advanced_search(
        self,
        spec: SearchSpec,
        page: PageModel | None = None,
        sort: SortModel | None = None,
    ) -> IndexSearchResult: ...

    @abc.abstractmethod
    async def get_index_mapping(self) -> dict[str, Any]: ...
