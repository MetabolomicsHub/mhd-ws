from __future__ import annotations

import datetime
from logging import getLogger
from typing import Annotated, Any, Literal

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import JSONResponse
from fastapi.openapi.models import Example
from pydantic import Field

from mhd_ws.application.services.interfaces.advanced_search_port import (
    AdvancedSearchPort,
)
from mhd_ws.application.services.interfaces.search_port import SearchPort
from mhd_ws.domain.domain_services.search_spec_resolver import SearchSpecResolver
from mhd_ws.domain.entities.search.dtos import (
    ComparatorClauseDTO,
    DescriptorClauseDTO,
    PageDTO,
    ParameterPairClauseDTO,
    SearchRequestDTO,
    SortDTO,
    TermClauseDTO,
)
from mhd_ws.domain.entities.search.index_search import (
    FilterModel,
    IndexSearchResult,
    PageModel,
    SortModel,
)
from mhd_ws.domain.entities.search.index_search_spec import Target, ValueType
from mhd_ws.domain.entities.search.registries.models import (
    AllowedOperators,
    FieldDef,
    FieldRegistry,
)
from mhd_ws.domain.shared.model import MhdBaseModel
from mhd_ws.presentation.rest_api.core.responses import APIResponse

logger = getLogger(__name__)

router = APIRouter(tags=["MetabolomicsHub Search"], prefix="/v0_1")


# -- response models ----------------------------------------------------------


class FieldDefPublic(MhdBaseModel):
    field_id: str
    description: str
    target: Target
    value_type: ValueType
    ops: AllowedOperators
    facet_key: str | None = None
    facet_type: Literal["value", "range", "date_histogram"] | None = None


class SearchFieldsResponse(MhdBaseModel):
    fields: list[FieldDefPublic]


class AdvancedSearchExamplesResponse(MhdBaseModel):
    minimal: SearchRequestDTO
    full: SearchRequestDTO


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


_ADVANCED_SEARCH_DESCRIPTION = """Search datasets using field-level clauses and optional free-text.

**Example: Simple text search**
```json
{"query_text": "cancer metabolomics"}
```

**Example: Sample count filter with disease terms**

Show studies with more than 20 samples and either of the specified diseases:
```json
{
  "clauses": [
    {"kind": "compare", "field_id": "samples_count", "op": "GT", "value": 20},
    {
      "kind": "terms", "field_id": "facet_diseases", "op": "OR",
      "terms": ["Liver Depression and Qi Stagnation", "Infected with SARS-CoV-2"],
      "match": "EXACT"
    }
  ],
  "page": {"current": 1, "size": 20}
}
```

**Example: Two-stage metabolite join**

Find lipidomics datasets from human studies containing cholesterol or triglyceride:
```json
{
  "query_text": "lipidomics",
  "inter_field_combiner": "AND",
  "clauses": [
    {"kind": "terms", "field_id": "facet_organisms", "op": "OR", "terms": ["Homo sapiens"], "match": "EXACT"},
    {"kind": "terms", "field_id": "metabolite_name", "op": "OR", "terms": ["cholesterol", "triglyceride"], "match": "AUTO"}
  ],
  "page": {"current": 1, "size": 20}
}
```

**Example: Negated clause**

Exclude datasets associated with diabetes:
```json
{
  "clauses": [
    {"kind": "terms", "field_id": "facet_diseases", "op": "OR", "terms": ["diabetes"], "match": "EXACT", "not": true}
  ]
}
```

**Example: Parameter pair clause**

Find positive scan polarity MS datasets and return the scan polarity value distribution in the facets:
```json
{
  "clauses": [
    {
      "kind": "parameter_pair",
      "type_name": "scan polarity",
      "values": ["positive"],
      "op": "OR",
      "include_facet": true
    }
  ],
  "page": {"current": 1, "size": 20}
}
```

Use `"values": []` to match any dataset that has the parameter type regardless of value.
Set `"include_facet": true` to receive the full value distribution for that parameter type in the response facets.

**Example: Descriptor clause**

Find datasets tagged with a specific ontology term via a known relationship. The `relationship` field
disambiguates which part of the graph the descriptor was attached to:
```json
{
  "clauses": [
    {
      "kind": "descriptor",
      "relationship": "study.has-submitter-keyword",
      "names": ["COVID-19", "Lung Injury"],
      "op": "OR"
    }
  ],
  "page": {"current": 1, "size": 20}
}
```

Common `relationship` values: `"study.has-submitter-keyword"`, `"study.has-repository-keyword"`,
`"assay.omics_type"`, `"assay.technology_type"`, `"assay.measurement_type"`, `"assay.assay_type"`,
`"metadata-file.format"`, `"raw-data-file.format"`.
Use `"op": "AND"` to require all named descriptors to be present on the same relationship.
"""

_ADVANCED_SEARCH_EXAMPLES = {
    "Simple text search": Example(
        summary="Simple text search",
        description="Free-text query across all dataset fields.",
        value={"query_text": "cancer metabolomics"},
    ),
    "Sample count + disease filter": Example(
        summary="Sample count filter with disease terms",
        description=(
            "Show studies with more than 20 samples and either of the specified diseases."
        ),
        value={
            "clauses": [
                {"kind": "compare", "field_id": "samples_count", "op": "GT", "value": 20},
                {
                    "kind": "terms",
                    "field_id": "facet_diseases",
                    "op": "OR",
                    "terms": [
                        "Liver Depression and Qi Stagnation",
                        "Infected with SARS-CoV-2",
                    ],
                    "match": "EXACT",
                },
            ],
            "page": {"current": 1, "size": 20},
        },
    ),
    "Two-stage metabolite join": Example(
        summary="Two-stage metabolite join",
        description=(
            "Find lipidomics datasets from human studies containing cholesterol or triglyceride. "
            "Stage 1 queries the metabolite index; stage 2 filters the dataset index by the resulting IDs."
        ),
        value={
            "query_text": "lipidomics",
            "inter_field_combiner": "AND",
            "clauses": [
                {
                    "kind": "terms",
                    "field_id": "facet_organisms",
                    "op": "OR",
                    "terms": ["Homo sapiens"],
                    "match": "EXACT",
                },
                {
                    "kind": "terms",
                    "field_id": "metabolite_name",
                    "op": "OR",
                    "terms": ["cholesterol", "triglyceride"],
                    "match": "AUTO",
                },
            ],
            "page": {"current": 1, "size": 20},
        },
    ),
    "Negated clause": Example(
        summary="Negated clause",
        description="Exclude datasets associated with diabetes.",
        value={
            "clauses": [
                {
                    "kind": "terms",
                    "field_id": "facet_diseases",
                    "op": "OR",
                    "terms": ["diabetes"],
                    "match": "EXACT",
                    "not": True,
                }
            ]
        },
    ),
    "Parameter pair clause": Example(
        summary="Parameter pair clause with facet drill-down",
        description=(
            "Find positive-polarity MS datasets. "
            "Setting include_facet: true returns the full scan polarity value distribution in the response facets."
        ),
        value={
            "clauses": [
                {
                    "kind": "parameter_pair",
                    "type_name": "scan polarity",
                    "values": ["positive"],
                    "op": "OR",
                    "include_facet": True,
                }
            ],
            "page": {"current": 1, "size": 20},
        },
    ),
    "Descriptor clause": Example(
        summary="Descriptor clause — relationship-qualified ontology tag search",
        description=(
            "Find datasets tagged with COVID-19 or Lung Injury as submitter keywords. "
            "The relationship field scopes the match to descriptors attached via a specific "
            "graph relationship, preventing false matches from the same term appearing in "
            "a different context (e.g. as a file format or assay type)."
        ),
        value={
            "clauses": [
                {
                    "kind": "descriptor",
                    "relationship": "study.has-submitter-keyword",
                    "names": ["COVID-19", "Lung Injury"],
                    "op": "OR",
                }
            ],
            "page": {"current": 1, "size": 20},
        },
    ),
}


@router.post(
    "/search/advanced/datasets",
    summary="Advanced dataset search",
    description=_ADVANCED_SEARCH_DESCRIPTION,
    response_model=APIResponse[IndexSearchResult],
    responses={
        200: {"description": "Search results."},
        400: {"description": "Bad request."},
    },
    include_in_schema=True,
)
@inject
async def advanced_search_datasets(
    request: SearchRequestDTO = Body(openapi_examples=_ADVANCED_SEARCH_EXAMPLES),
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
    "/search/fields",
    summary="Get searchable fields",
    description="Returns all searchable fields and their allowed operators for building advanced search queries.",
    response_model=APIResponse[SearchFieldsResponse],
    responses={
        200: {"description": "Field registry."},
    },
    include_in_schema=True,
)
@inject
async def get_search_fields(
    field_registry: FieldRegistry = Depends(Provide["gateways.field_registry"]),  # noqa: FAST002
) -> APIResponse[SearchFieldsResponse]:
    return APIResponse(
        content=SearchFieldsResponse(
            fields=[
                FieldDefPublic(**f.model_dump(exclude={"field_key"}))
                for f in field_registry.fields
            ]
        )
    )


@router.get(
    "/search/advanced/datasets/example",
    summary="Get advanced search request examples",
    description=(
        "Returns ready-to-use request payload examples for "
        "POST /v0_1/search/advanced/datasets."
    ),
    response_model=APIResponse[AdvancedSearchExamplesResponse],
    responses={
        200: {"description": "Advanced search request payload examples."},
    },
    include_in_schema=True,
)
@inject
async def get_advanced_search_examples(
    field_registry: FieldRegistry = Depends(Provide["gateways.field_registry"]),  # noqa: FAST002
) -> APIResponse[AdvancedSearchExamplesResponse]:
    return APIResponse(
        content=AdvancedSearchExamplesResponse(
            minimal=SearchRequestDTO(),
            full=_build_advanced_search_example(field_registry),
        )
    )


@router.get(
    "/search/advanced/datasets/mapping",
    summary="Get advanced dataset search index mapping",
    description="Returns the Elasticsearch index mapping for the MS dataset index used by the advanced search pipeline.",
    responses={
        200: {"description": "Index mapping."},
    },
    include_in_schema=True,
)
@inject
async def get_advanced_dataset_search_mapping(
    gateway: AdvancedSearchPort = Depends(Provide["gateways.advanced_search_gateway"]),  # noqa: FAST002
) -> JSONResponse:
    mapping = await gateway.get_index_mapping()
    return JSONResponse(content=mapping)


@router.get(
    "/search/datasets/mapping",
    summary="Get dataset search index mapping",
    description="Returns the Elasticsearch index mapping for the legacy dataset index.",
    responses={
        200: {"description": "Index mapping."},
    },
    include_in_schema=True,
)
@inject
async def get_dataset_search_mapping(
    gateway: SearchPort = Depends(Provide["gateways.elasticsearch_legacy_gateway"]),  # noqa: FAST002
) -> JSONResponse:
    mapping = await gateway.get_index_mapping()
    return JSONResponse(content=mapping)


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


def _build_advanced_search_example(field_registry: FieldRegistry) -> SearchRequestDTO:
    clauses: list[TermClauseDTO | ComparatorClauseDTO | ParameterPairClauseDTO | DescriptorClauseDTO] = []

    dataset_term_field = _find_field(
        field_registry, target=Target.DATASET, require_terms=True
    )
    if dataset_term_field:
        clauses.append(_build_term_clause_example(dataset_term_field))

    metabolite_term_field = _find_field(
        field_registry, target=Target.METABOLITE, require_terms=True
    )
    if metabolite_term_field:
        clauses.append(_build_term_clause_example(metabolite_term_field))

    dataset_comparator_field = _find_field(
        field_registry, target=Target.DATASET, require_comparators=True
    )
    if dataset_comparator_field:
        clauses.append(_build_comparator_clause_example(dataset_comparator_field))

    clauses.append(
        ParameterPairClauseDTO(
            type_name="scan polarity",
            values=["positive"],
            op="OR",
            include_facet=True,
        )
    )

    clauses.append(
        DescriptorClauseDTO(
            relationship="study.has-submitter-keyword",
            names=["COVID-19"],
            op="OR",
        )
    )

    return SearchRequestDTO(
        query_text="glucose",
        inter_field_combiner="AND",
        clauses=clauses,
        page=PageDTO(current=1, size=25),
        sort=[SortDTO(field="_score", direction="desc")],
    )


def _find_field(
    field_registry: FieldRegistry,
    target: Target | None = None,
    require_terms: bool = False,
    require_comparators: bool = False,
) -> FieldDef | None:
    for field in field_registry.fields:
        if target is not None and field.target != target:
            continue
        if require_terms and not field.ops.allow_terms:
            continue
        if require_comparators and not field.ops.allow_comparators:
            continue
        return field
    return None


def _build_term_clause_example(field: FieldDef) -> TermClauseDTO:
    match_mode = (
        field.ops.allowed_match_modes[0]
        if field.ops.allowed_match_modes
        else "AUTO"
    )
    intra_combiner = (
        field.ops.allowed_intra_combiners[0]
        if field.ops.allowed_intra_combiners
        else "OR"
    )
    value = _example_value_for_field(field)
    return TermClauseDTO(
        field_id=field.field_id,
        op=intra_combiner,
        terms=[str(value)],
        match=match_mode,
    )


def _build_comparator_clause_example(field: FieldDef) -> ComparatorClauseDTO:
    comparator = (
        field.ops.allowed_comparators[0]
        if field.ops.allowed_comparators
        else "EQ"
    )
    return ComparatorClauseDTO(
        field_id=field.field_id,
        op=comparator,
        value=_example_value_for_field(field),
    )


def _example_value_for_field(field: FieldDef) -> str | int | float:
    if field.value_type == ValueType.NUMBER:
        return 1
    if field.value_type == ValueType.DATE:
        return "2025-01-01"
    if field.target == Target.METABOLITE:
        return "glucose"
    if field.target == Target.DATASET:
        return "MTBLS1234"
    return "example"
