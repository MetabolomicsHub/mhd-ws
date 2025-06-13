import datetime
from logging import getLogger
from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Body, Depends, Query
from fastapi.openapi.models import Example
from metabolights_utils.common import CamelCaseModel
from pydantic import Field

from mhd_ws.application.services.interfaces.cache_service import CacheService
from mhd.model.v0_1.announcement.profiles.base.profile import AnnouncementBaseProfile

logger = getLogger(__name__)

router = APIRouter(tags=["MetabolomicsHub Search"], prefix="/v0_1")


class FilterOption(CamelCaseModel):
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


class SortOption(CamelCaseModel):
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


class SearchOptions(CamelCaseModel):
    filter_options: Annotated[
        None | list[FilterOption],
        Field(title="Filter Options", description="Defined filters"),
    ] = None
    sort_options: Annotated[
        None | list[SortOption], Field(title="Sort Options", description="Sort options")
    ] = None


class DatasetSearchResult(CamelCaseModel):
    skip: Annotated[
        int, Field(title="Skipped results", description="Skipped results.")
    ] = 0
    size: Annotated[
        int, Field(title="Current result size", description="Current result size.")
    ] = 50
    datasets: Annotated[
        list[AnnouncementBaseProfile],
        Field(
            title="Matched MetabolomExchage Dataset List",
            description="Matched MetabolomExchage Dataset List",
        ),
    ]


class DatasetFileSearchResult(CamelCaseModel):
    skip: Annotated[
        int, Field(title="Skipped results", description="Skipped results.")
    ] = 0
    size: Annotated[
        int, Field(title="Current result size", description="Current result size.")
    ] = 50
    files: Annotated[
        list[AnnouncementBaseProfile],
        Field(
            title="Matched MetabolomExchage Dataset File List",
            description="Matched MetabolomExchage Dataset File List",
        ),
    ]


@router.post(
    "/datasets/searches",
    summary="Search datasets",
    description="Search Datasets",
    response_model=DatasetSearchResult,
    responses={
        201: {
            "description": "New MHD identifier is created.",
        },
        401: {
            "description": "Unauthorized request.",
        },
    },
    include_in_schema=False,
)
@inject
async def request_new_identifier(
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
    cache_service: CacheService = Depends(
        Provide["services.cache_service"]
    ),  # noqa: FAST002
):
    # return DatasetSearchResult(
    #     datasets=[Announcement.model_validate(example_announcement)]
    # )
    pass


@router.post(
    "/dataset-files/searches",
    summary="Search datasets",
    description="Search Datasets",
    response_model=DatasetFileSearchResult,
    responses={
        201: {
            "description": "New MHD identifier is created.",
        },
        401: {
            "description": "Unauthorized request.",
        },
    },
    include_in_schema=False,
)
@inject
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
    cache_service: CacheService = Depends(
        Provide["services.cache_service"]
    ),  # noqa: FAST002
):
    # files = Announcement.model_validate(example_announcement).raw_data_file_uri_list
    # if len(files) > 10:
    #     files = files[:10]
    return DatasetFileSearchResult(files=None)


@router.post(
    "/dataset-metadata-files/searches",
    summary="Search dataset metadata files",
    description="Search dataset metadata files",
    response_model=DatasetFileSearchResult,
    responses={
        200: {
            "description": "Search results.",
        },
        400: {
            "description": "Bad request.",
        },
    },
    include_in_schema=False,
)
@inject
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
    cache_service: CacheService = Depends(
        Provide["services.cache_service"]
    ),  # noqa: FAST002
):
    # files = Announcement.model_validate(
    #     example_announcement
    # ).repository_metadata_file_uri_list
    # if len(files) > 10:
    #     files = files[:10]
    # return DatasetFileSearchResult(files=files)
    pass
