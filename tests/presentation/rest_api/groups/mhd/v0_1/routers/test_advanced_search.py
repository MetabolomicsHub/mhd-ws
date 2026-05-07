from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dependency_injector import containers, providers
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mhd_ws.application.services.interfaces.advanced_search_port import (
    AdvancedSearchPort,
)
from mhd_ws.domain.domain_services.search_spec_resolver import SearchSpecResolver
from mhd_ws.domain.entities.search.advanced_core import SearchSpec
from mhd_ws.domain.entities.search.index_search import (
    FacetBucket,
    FacetResponse,
    IndexSearchResult,
    PageModel,
    SortModel,
)
from mhd_ws.domain.entities.search.registries.field_registry import FIELD_REGISTRY
from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers import search_endpoints


@dataclass
class SpyAdvancedSearchGateway(AdvancedSearchPort):
    result: IndexSearchResult
    received_spec: SearchSpec | None = None
    received_page: PageModel | None = None
    received_sort: SortModel | None = None

    async def advanced_search(
        self,
        spec: SearchSpec,
        page: PageModel | None = None,
        sort: SortModel | None = None,
    ) -> IndexSearchResult:
        self.received_spec = spec
        self.received_page = page
        self.received_sort = sort
        return self.result

    async def get_index_mapping(self) -> dict[str, Any]:
        return {}


class RouterTestContainer(containers.DeclarativeContainer):
    gateways = providers.DependenciesContainer()


def _build_test_client(gateway: SpyAdvancedSearchGateway) -> TestClient:
    app = FastAPI()
    app.include_router(search_endpoints.router)

    resolver = SearchSpecResolver(FIELD_REGISTRY)

    container = RouterTestContainer()
    container.gateways.search_spec_resolver.override(providers.Object(resolver))
    container.gateways.advanced_search_gateway.override(providers.Object(gateway))
    container.wire(modules=[search_endpoints])
    app.container = container

    client = TestClient(app)
    client._di_container = container  # type: ignore[attr-defined]
    return client


def test_advanced_search_endpoint_translates_request_and_wraps_response() -> None:
    gateway = SpyAdvancedSearchGateway(
        result=IndexSearchResult(
            results=[{"_id": "MTBLS1", "study": {"title": "Cancer study"}}],
            total_results=1,
            facets={
                "organisms": FacetResponse(
                    type="value",
                    data=[FacetBucket(value="Homo sapiens", count=2)],
                )
            },
            request_id="req-123",
        )
    )
    client = _build_test_client(gateway)

    try:
        response = client.post(
            "/v0_1/search/advanced/datasets",
            json={
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
                        "kind": "characteristic_pair",
                        "type_name": "  Cell Line ",
                        "values": ["MCF7"],
                        "include_facet": True,
                    },
                ],
                "page": {"current": 2, "size": 10},
                "sort": [
                    {"field": "study.title.keyword", "direction": "asc"},
                    {"field": "_score", "direction": "desc"},
                ],
            },
        )
    finally:
        client._di_container.unwire()  # type: ignore[attr-defined]

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "successMessage": None,
        "errorMessage": None,
        "errors": [],
        "content": {
            "results": [{"_id": "MTBLS1", "study": {"title": "Cancer study"}}],
            "totalResults": 1,
            "facets": {
                "organisms": {
                    "type": "value",
                    "data": [{"value": "Homo sapiens", "count": 2}],
                }
            },
            "requestId": "req-123",
        },
    }

    assert gateway.received_page == PageModel(current=2, size=10)
    assert gateway.received_sort == SortModel(
        field="study.title.keyword", direction="asc"
    )
    assert gateway.received_spec is not None
    assert gateway.received_spec.query_text == "lipidomics"
    assert gateway.received_spec.inter_field_combiner == "AND"
    assert gateway.received_spec.clauses[0].field.field_key == "dataset.facets.organisms"
    assert gateway.received_spec.clauses[1].type_name == "cell line"
    assert gateway.received_spec.clauses[1].include_facet is True


def test_advanced_search_endpoint_uses_optional_page_and_sort_defaults() -> None:
    gateway = SpyAdvancedSearchGateway(result=IndexSearchResult(request_id="req-456"))
    client = _build_test_client(gateway)

    try:
        response = client.post(
            "/v0_1/search/advanced/datasets",
            json={"query_text": "proteomics"},
        )
    finally:
        client._di_container.unwire()  # type: ignore[attr-defined]

    assert response.status_code == 200
    assert response.json()["content"]["requestId"] == "req-456"
    assert gateway.received_page is None
    assert gateway.received_sort is None
    assert gateway.received_spec is not None
    assert gateway.received_spec.query_text == "proteomics"
    assert gateway.received_spec.clauses == []
