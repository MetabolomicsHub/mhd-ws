from __future__ import annotations

from typing import Any

from mhd_ws.domain.entities.search.advanced_core.predicates import BoolExpr
from mhd_ws.domain.entities.search.advanced_core.registries import (
    FieldDef,
    IndexCapabilities,
)
from mhd_ws.infrastructure.search.es.es_dsl_compiler_core import (
    GenericEsDslCompiler,
)
from mhd_ws.infrastructure.search.es.es_dsl_compiler_mhd_extension import (
    MhdDslCompilerExtension,
)


class EsDslCompiler:
    """Stable facade that preserves the old API during compiler extraction.

    Generic ES DSL compilation now lives in ``es_dsl_compiler_core`` while the
    MHD-specific pair predicates and drill-down aggregations live in
    ``es_dsl_compiler_mhd_extension``. Keeping this wrapper lets the gateway
    and tests remain unchanged while the package boundary settles.
    """

    def __init__(self, index_caps: IndexCapabilities) -> None:
        self._core = GenericEsDslCompiler(
            index_caps,
            extensions=(MhdDslCompilerExtension(),),
        )
        self._mhd_extension = MhdDslCompilerExtension()

    def compile_query(self, expr: BoolExpr) -> dict[str, Any]:
        return self._core.compile_query(expr)

    def compile_pagination(self, page_current: int, page_size: int) -> dict[str, Any]:
        return self._core.compile_pagination(page_current, page_size)

    def compile_sort(self, field: str, direction: str) -> list[dict[str, Any]]:
        return self._core.compile_sort(field, direction)

    def compile_facet_aggs(
        self, facet_fields: list[FieldDef], facet_size: int = 25
    ) -> dict[str, Any]:
        return self._core.compile_facet_aggs(facet_fields, facet_size)

    def compile_metabolite_composite_agg(
        self, dataset_id_es_path: str, page_size: int
    ) -> dict[str, Any]:
        return self._core.compile_id_terms_composite_agg(
            agg_name="dataset_ids",
            source_name="dataset_id",
            field_es_path=dataset_id_es_path,
            page_size=page_size,
        )

    def compile_characteristic_group_aggs(
        self, type_names: list[str], facet_size: int = 25
    ) -> dict[str, Any]:
        return self._mhd_extension.compile_characteristic_group_aggs(
            self._core, type_names, facet_size
        )

    def compile_parameter_group_aggs(
        self, type_names: list[str], facet_size: int = 25
    ) -> dict[str, Any]:
        return self._mhd_extension.compile_parameter_group_aggs(
            self._core, type_names, facet_size
        )
