from __future__ import annotations

import abc
from typing import Any

from mhd_ws.domain.entities.search.index_search import (
    FilterModel,
    IndexSearchResult,
    PageModel,
    SortModel,
)


class SearchPort(abc.ABC):
    @abc.abstractmethod
    async def search(
        self,
        *,
        search_text: str | None = None,
        filters: list[FilterModel] | None = None,
        page: PageModel | None = None,
        sort: SortModel | None = None,
    ) -> IndexSearchResult: ...

    @abc.abstractmethod
    async def get_index_mapping(self) -> dict[str, Any]: ...
