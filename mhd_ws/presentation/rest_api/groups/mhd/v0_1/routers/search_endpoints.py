from __future__ import annotations

import datetime
from logging import getLogger
from typing import Annotated, Any

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Body, Depends, Query
from fastapi.openapi.models import Example
from pydantic import Field

from mhd_ws.application.services.interfaces.advanced_search_port import (
    AdvancedSearchPort,
)
from mhd_ws.application.services.interfaces.search_port import SearchPort
from mhd_ws.domain.domain_services.search_spec_resolver import SearchSpecResolver
from mhd_ws.domain.entities.search.dtos import SearchRequestDTO
from mhd_ws.domain.entities.search.index_search import (
    FilterModel,
    IndexSearchResult,
    PageModel,
    SortModel,
)
from mhd_ws.domain.shared.model import MhdBaseModel
from mhd_ws.presentation.rest_api.core.responses import APIResponse

logger = getLogger(__name__)

router = APIRouter(tags=["MetabolomicsHub Search"], prefix="/v0_1")


# -- request models -----------------------------------------------------------


class FilterOption(MhdBaseModel):
    filter_name: Annotated[
        str,
        Field(
            title="Filter name.",
            description="Selected filter name. Filter names will be defined later.",
        ),
    ]
    operation: Annotated[
        str,
        Field(
            title="Filter operation.",
            description="Selected filter operation. Examples, equal, contains, startswith, endswith, etc.",
        ),
    ] = "equal"
    value: Annotated[
        datetime.datetime | str | int | bool,
        Field(
            title="Filter value.",
            description="filter value.",
        ),
    ]


class SortOption(MhdBaseModel):
    field_name: Annotated[
        str,
        Field(
            title="Field name.",
            description="Selected filter name. Filter names will be defined later.",
        ),
    ]
    descending: Annotated[
        bool,
        Field(
            title="Sort in descending order.",
            description="Sort in descending order",
        ),
    ] = False


class SearchOptions(MhdBaseModel):
    filter_options: Annotated[
        None | list[FilterOption],
        Field(title="Filter Options", description="Defined filters"),
    ] = None
    sort_options: Annotated[
        None | list[SortOption], Field(title="Sort Options", description="Sort options")
    ] = None


# -- endpoints ----------------------------------------------------------------


@router.post(
    "/search/datasets",
    summary="Search datasets",
    description="Search Datasets",
    response_model=APIResponse[IndexSearchResult],
    responses={
        200: {"description": "Search results."},
        400: {"description": "Bad request."},
    },
    include_in_schema=True,
)
@inject
async def search_datasets(
    search: Annotated[
        None | str,
        Query(
            title="Dataset search keywords.",
            description="Dataset search keywords.",
        ),
    ] = None,
    search_options: Annotated[
        None | SearchOptions,
        Body(
            title="Search Options",
            description="Search Options",
            openapi_examples={
                "No Search Option": Example(
                    summary="No Search Option",
                    value={},
                ),
                "Example Search Option ": Example(
                    summary="Example Search Option",
                    value=SearchOptions(
                        filter_options=[
                            FilterOption(filter_name="disease", value="cancer")
                        ],
                        sort_options=[
                            SortOption(field_name="mhdIdentifier", descending=True)
                        ],
                    ).model_dump(by_alias=True),
                ),
            },
        ),
    ] = None,
    skip: Annotated[
        int, Query(title="Skip n results", description="Skip n results.")
    ] = 0,
    size: Annotated[
        int,
        Query(title="Size of returned result", description="Size of returned result."),
    ] = 50,
    gateway: SearchPort = Depends(Provide["gateways.elasticsearch_legacy_gateway"]),  # noqa: FAST002
) -> APIResponse[IndexSearchResult]:
    filters = _build_filters(search_options)
    page_size = max(1, min(size, 200))
    current_page = (skip // page_size) + 1 if page_size else 1
    page = PageModel(current=current_page, size=page_size)

    result = await gateway.search(
        search_text=search,
        filters=filters,
        page=page,
    )
    return APIResponse(content=result)


@router.post(
    "/search/advanced/datasets",
    summary="Advanced dataset search",
    description="Search datasets using the advanced search pipeline with field-level clauses.",
    response_model=APIResponse[IndexSearchResult],
    responses={
        200: {"description": "Search results."},
        400: {"description": "Bad request."},
    },
    include_in_schema=True,
)
@inject
async def advanced_search_datasets(
    request: SearchRequestDTO = Body(...),
    resolver: SearchSpecResolver = Depends(Provide["gateways.search_spec_resolver"]),  # noqa: FAST002
    gateway: AdvancedSearchPort = Depends(Provide["gateways.advanced_search_gateway"]),  # noqa: FAST002
) -> APIResponse[IndexSearchResult]:
    spec = resolver.resolve(request)
    page = (
        PageModel(current=request.page.current, size=request.page.size)
        if request.page
        else None
    )
    sort = (
        SortModel(field=request.sort[0].field, direction=request.sort[0].direction)
        if request.sort
        else None
    )
    result = await gateway.advanced_search(spec, page=page, sort=sort)
    return APIResponse(content=result)


@router.get(
    "/search/datasets/mapping",
    summary="Get dataset search index mapping",
    description="Returns the Elasticsearch index mapping for the legacy dataset index.",
    response_model=APIResponse[dict[str, Any]],
    responses={
        200: {"description": "Index mapping."},
    },
    include_in_schema=True,
)
@inject
async def get_dataset_search_mapping(
    gateway: SearchPort = Depends(Provide["gateways.elasticsearch_legacy_gateway"]),  # noqa: FAST002
) -> APIResponse[dict[str, Any]]:
    mapping = await gateway.get_index_mapping()
    return APIResponse(content=mapping)


@router.post(
    "/search/dataset-files",
    summary="Search dataset files",
    description="Search Dataset files",
    include_in_schema=False,
)
async def search_dataset_files(
    search: Annotated[
        None | str,
        Query(
            title="Dataset search keywords.",
            description="Dataset search keywords.",
        ),
    ] = None,
    search_options: Annotated[
        None | SearchOptions,
        Body(
            title="Search Options",
            description="Search Options",
            openapi_examples={
                "No Search Option": Example(
                    summary="No Search Option",
                    value={},
                ),
            },
        ),
    ] = None,
    skip: Annotated[
        int, Query(title="Skip n results", description="Skip n results.")
    ] = 0,
    size: Annotated[
        int,
        Query(title="Size of returned result", description="Size of returned result."),
    ] = 50,
) -> None:
    pass


@router.post(
    "/search/dataset-metadata-files",
    summary="Search dataset metadata files",
    description="Search dataset metadata files",
    include_in_schema=False,
)
async def search_dataset_metadata_files(
    search: Annotated[
        None | str,
        Query(
            title="Dataset search keywords.",
            description="Dataset search keywords.",
        ),
    ] = None,
    search_options: Annotated[
        None | SearchOptions,
        Body(
            title="Search Options",
            description="Search Options",
            openapi_examples={
                "No Search Option": Example(
                    summary="No Search Option",
                    value={},
                ),
            },
        ),
    ] = None,
    skip: Annotated[
        int, Query(title="Skip n results", description="Skip n results.")
    ] = 0,
    size: Annotated[
        int,
        Query(title="Size of returned result", description="Size of returned result."),
    ] = 50,
) -> None:
    pass


# -- helpers ------------------------------------------------------------------


def _build_filters(search_options: SearchOptions | None) -> list[FilterModel] | None:
    if not search_options or not search_options.filter_options:
        return None
    filters: list[FilterModel] = []
    for opt in search_options.filter_options:
        filters.append(
            FilterModel(
                field=opt.filter_name,
                values=[str(opt.value)],
                operator="any",
            )
        )
    return filters or None
