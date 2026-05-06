import pytest

from mhd_ws.domain.domain_services.query_planner import PlannerConfig, QueryPlanner
from mhd_ws.domain.domain_services.search_spec_resolver import SearchSpecResolver
from mhd_ws.domain.entities.search.advanced_core import Target
from mhd_ws.domain.entities.search.dtos import (
    CharacteristicPairClauseDTO,
    ParameterPairClauseDTO,
    SearchRequestDTO,
    TermClauseDTO,
)
from mhd_ws.domain.entities.search.index_search import PageModel, SortModel
from mhd_ws.domain.entities.search.registries.field_registry import FIELD_REGISTRY
from mhd_ws.domain.entities.search.registries.index_capability_registry import (
    build_index_capabilities,
)
from mhd_ws.infrastructure.search.es.advanced_search_gateway import (
    AdvancedSearchGateway,
)
from mhd_ws.infrastructure.search.es.es_configuration import (
    AdvancedSearchConfiguration,
)


class FakeElasticsearchClient:
    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self.search_calls: list[dict] = []

    async def search(
        self, index: str, body: dict, api_key_name: str | None = None
    ) -> dict:
        self.search_calls.append(
            {"index": index, "body": body, "api_key_name": api_key_name}
        )
        if not self._responses:
            raise AssertionError("Unexpected search call")
        return self._responses.pop(0)


def _build_gateway(client: FakeElasticsearchClient) -> AdvancedSearchGateway:
    return AdvancedSearchGateway(
        client=client,
        config=AdvancedSearchConfiguration(),
        planner=QueryPlanner(PlannerConfig(join_target=Target.METABOLITE)),
        index_registry=build_index_capabilities(),
        field_registry=FIELD_REGISTRY,
    )


@pytest.mark.asyncio
async def test_dataset_stage_maps_results_and_generic_facets() -> None:
    client = FakeElasticsearchClient(
        [
            {
                "hits": {
                    "total": {"value": 2},
                    "hits": [
                        {
                            "_id": "MTBLS1",
                            "_score": 4.2,
                            "_source": {"study": {"title": "Cancer study"}},
                        }
                    ],
                },
                "aggregations": {
                    "organisms": {
                        "buckets": [{"key": "Homo sapiens", "doc_count": 2}]
                    },
                    "submission_date": {
                        "buckets": [
                            {
                                "key": 2024,
                                "key_as_string": "2024",
                                "from": "2024-01-01",
                                "to": "2025-01-01",
                                "doc_count": 1,
                            }
                        ]
                    },
                },
            }
        ]
    )
    gateway = _build_gateway(client)
    resolver = SearchSpecResolver(FIELD_REGISTRY)
    spec = resolver.resolve(
        SearchRequestDTO(
            clauses=[
                TermClauseDTO(
                    field_id="dataset_title",
                    op="AND",
                    terms=["cancer"],
                    match="AUTO",
                )
            ]
        )
    )

    result = await gateway.advanced_search(
        spec,
        page=PageModel(current=2, size=5),
        sort=SortModel(field="study.title.keyword", direction="asc"),
    )

    assert result.total_results == 2
    assert result.results == [
        {
            "study": {"title": "Cancer study"},
            "_id": "MTBLS1",
            "_score": 4.2,
        }
    ]
    assert result.facets["organisms"].type == "value"
    assert result.facets["organisms"].data[0].value == "Homo sapiens"
    assert result.facets["submission_date"].type == "range"
    assert result.facets["submission_date"].data[0].value == "2024"
    assert result.request_id

    assert len(client.search_calls) == 1
    call = client.search_calls[0]
    assert call["index"] == "dataset_ms_v1"
    assert call["api_key_name"] == "dataset_ms"
    assert call["body"]["from"] == 5
    assert call["body"]["size"] == 5
    assert call["body"]["sort"] == [{"study.title.keyword": {"order": "asc"}}]
    assert call["body"]["query"] == {"match": {"study.title": "cancer"}}


@pytest.mark.asyncio
async def test_join_stage_applies_dataset_id_filter_and_maps_drilldown_facets() -> None:
    client = FakeElasticsearchClient(
        [
            {
                "aggregations": {
                    "dataset_ids": {
                        "buckets": [
                            {"key": {"dataset_id": "MTBLS1"}},
                            {"key": {"dataset_id": "MTBLS2"}},
                        ]
                    }
                }
            },
            {
                "hits": {
                    "total": {"value": 1},
                    "hits": [
                        {
                            "_id": "MTBLS1",
                            "_score": 7.0,
                            "_source": {"study": {"title": "Lipidomics study"}},
                        }
                    ],
                },
                "aggregations": {
                    "param__scan polarity": {
                        "by_type": {
                            "values": {
                                "buckets": [
                                    {"key": "positive", "doc_count": 3},
                                ]
                            }
                        }
                    },
                    "char__cell line": {
                        "by_type": {
                            "values": {
                                "buckets": [
                                    {"key": "MCF7", "doc_count": 2},
                                ]
                            }
                        }
                    },
                },
            },
        ]
    )
    gateway = _build_gateway(client)
    resolver = SearchSpecResolver(FIELD_REGISTRY)
    spec = resolver.resolve(
        SearchRequestDTO(
            clauses=[
                TermClauseDTO(
                    field_id="metabolite_name",
                    op="OR",
                    terms=["cholesterol"],
                    match="AUTO",
                ),
                ParameterPairClauseDTO(
                    type_name="scan polarity",
                    values=["positive"],
                    include_facet=True,
                ),
                CharacteristicPairClauseDTO(
                    type_name="Cell Line",
                    values=["MCF7"],
                    include_facet=True,
                ),
            ]
        )
    )

    result = await gateway.advanced_search(spec)

    assert result.total_results == 1
    assert result.facets["scan polarity"].data[0].value == "positive"
    assert result.facets["cell line"].data[0].value == "MCF7"

    assert len(client.search_calls) == 2
    metabolite_call = client.search_calls[0]
    dataset_call = client.search_calls[1]

    assert metabolite_call["index"] == "metabolite_ms_v1"
    assert metabolite_call["body"]["size"] == 0
    assert "dataset_ids" in metabolite_call["body"]["aggs"]

    assert dataset_call["index"] == "dataset_ms_v1"
    dataset_filters = dataset_call["body"]["query"]["bool"]["filter"]
    assert {"terms": {"id": ["MTBLS1", "MTBLS2"]}} in dataset_filters
    assert "param__scan polarity" in dataset_call["body"]["aggs"]
    assert "char__cell line" in dataset_call["body"]["aggs"]
