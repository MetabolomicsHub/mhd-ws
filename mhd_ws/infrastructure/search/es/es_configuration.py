from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ElasticsearchConfiguration:
    api_key_name: str | None = None


@dataclass(frozen=True)
class NestedSearchField:
    path: str
    field: str


@dataclass(frozen=True)
class LegacyElasticSearchConfiguration(ElasticsearchConfiguration):
    index_name: str = "dataset_legacy_v1"
    api_key_name: str = "legacy"
    facet_size: int = 25

    search_fields: tuple[str, ...] = (
        "id^10",
        "study.title^5",
        "study.description^2",
        "search_text",
        "project.title^3",
        "data_provider.accession^5",
    )

    nested_search_fields: tuple[NestedSearchField, ...] = (
        NestedSearchField(path="people", field="full_name"),
        NestedSearchField(path="publications", field="title"),
        NestedSearchField(path="organizations", field="name"),
        NestedSearchField(path="protocols", field="name"),
    )

    source_includes: list[str] = field(
        default_factory=lambda: [
            "id",
            "profile",
            "repository",
            "study",
            "dates",
            "data_provider",
            "facets",
            "assays",
            "samples",
            "files",
            "people",
            "organizations",
            "project",
            "publications",
            "protocols",
            "instruments",
            "mass_analyzers",
            "parameters",
            "factors",
        ]
    )


@dataclass(frozen=True)
class AdvancedSearchConfiguration(ElasticsearchConfiguration):
    api_key_name: str = "legacy"
    facet_size: int = 25
