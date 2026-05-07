from __future__ import annotations

from typing import Any

from mhd_ws.domain.entities.search.advanced_core.predicates import (
    BoolExpr,
    CharacteristicPairPredicate,
    DescriptorPredicate,
    ParameterPairPredicate,
)
from mhd_ws.infrastructure.search.es.es_dsl_compiler_core import (
    GenericEsDslCompiler,
)


class MhdDslCompilerExtension:
    def compile(
        self, expr: BoolExpr, compiler: GenericEsDslCompiler
    ) -> dict[str, Any] | None:
        if isinstance(expr, ParameterPairPredicate):
            return self._compile_parameter_pair(expr, compiler)
        if isinstance(expr, DescriptorPredicate):
            return self._compile_descriptor(expr, compiler)
        if isinstance(expr, CharacteristicPairPredicate):
            return self._compile_characteristic_pair(expr, compiler)
        return None

    def compile_parameter_group_aggs(
        self, compiler: GenericEsDslCompiler, type_names: list[str], facet_size: int = 25
    ) -> dict[str, Any]:
        type_path = compiler.get_es_path(
            "dataset.parameter_groups.type_name", "parameter_groups.type_name"
        )
        values_path = compiler.get_es_path(
            "dataset.parameter_groups.values", "parameter_groups.values"
        )

        aggs: dict[str, Any] = {}
        for type_name in type_names:
            key = f"param__{type_name}"
            aggs[key] = {
                "nested": {"path": "parameter_groups"},
                "aggs": {
                    "by_type": {
                        "filter": {"term": {type_path: type_name}},
                        "aggs": {
                            "values": {
                                "terms": {"field": values_path, "size": facet_size}
                            }
                        },
                    }
                },
            }
        return aggs

    def compile_characteristic_group_aggs(
        self, compiler: GenericEsDslCompiler, type_names: list[str], facet_size: int = 25
    ) -> dict[str, Any]:
        type_path = compiler.get_es_path(
            "dataset.characteristic_groups.type_name",
            "characteristic_groups.type_name",
        )
        values_path = compiler.get_es_path(
            "dataset.characteristic_groups.values", "characteristic_groups.values"
        )

        aggs: dict[str, Any] = {}
        for type_name in type_names:
            key = f"char__{type_name}"
            aggs[key] = {
                "nested": {"path": "characteristic_groups"},
                "aggs": {
                    "by_type": {
                        "filter": {"term": {type_path: type_name}},
                        "aggs": {
                            "values": {
                                "terms": {"field": values_path, "size": facet_size}
                            }
                        },
                    }
                },
            }
        return aggs

    def _compile_parameter_pair(
        self, pred: ParameterPairPredicate, compiler: GenericEsDslCompiler
    ) -> dict[str, Any]:
        type_path = compiler.get_es_path(
            "dataset.parameter_groups.type_name", "parameter_groups.type_name"
        )
        values_path = compiler.get_es_path(
            "dataset.parameter_groups.values", "parameter_groups.values"
        )
        return self._compile_pair_query(
            nested_path="parameter_groups",
            type_path=type_path,
            values_path=values_path,
            type_name=pred.type_name,
            values=pred.values,
            combiner=pred.combine_values,
        )

    def _compile_descriptor(
        self, pred: DescriptorPredicate, compiler: GenericEsDslCompiler
    ) -> dict[str, Any]:
        rel_path = compiler.get_es_path(
            "dataset.descriptors.relationship", "descriptors.relationship"
        )
        name_path = compiler.get_exact_es_path(
            "dataset.descriptors.name", "descriptors.name"
        )
        rel_filter: dict[str, Any] = {"term": {rel_path: pred.relationship}}

        if not pred.names:
            inner: dict[str, Any] = {"bool": {"filter": [rel_filter]}}
        elif len(pred.names) == 1:
            inner = {
                "bool": {"filter": [rel_filter, {"term": {name_path: pred.names[0]}}]}
            }
        elif pred.combine_names == "AND":
            inner = {
                "bool": {
                    "filter": [rel_filter]
                    + [{"term": {name_path: name}} for name in pred.names]
                }
            }
        else:
            inner = {
                "bool": {"filter": [rel_filter, {"terms": {name_path: pred.names}}]}
            }

        return {"nested": {"path": "descriptors", "query": inner}}

    def _compile_characteristic_pair(
        self, pred: CharacteristicPairPredicate, compiler: GenericEsDslCompiler
    ) -> dict[str, Any]:
        type_path = compiler.get_es_path(
            "dataset.characteristic_groups.type_name",
            "characteristic_groups.type_name",
        )
        values_path = compiler.get_es_path(
            "dataset.characteristic_groups.values", "characteristic_groups.values"
        )
        return self._compile_pair_query(
            nested_path="characteristic_groups",
            type_path=type_path,
            values_path=values_path,
            type_name=pred.type_name,
            values=pred.values,
            combiner=pred.combine_values,
        )

    @staticmethod
    def _compile_pair_query(
        *,
        nested_path: str,
        type_path: str,
        values_path: str,
        type_name: str,
        values: list[str],
        combiner: str,
    ) -> dict[str, Any]:
        type_filter: dict[str, Any] = {"term": {type_path: type_name}}

        if not values:
            inner: dict[str, Any] = {"bool": {"filter": [type_filter]}}
        elif len(values) == 1:
            inner = {
                "bool": {"filter": [type_filter, {"term": {values_path: values[0]}}]}
            }
        elif combiner == "AND":
            inner = {
                "bool": {
                    "filter": [type_filter]
                    + [{"term": {values_path: value}} for value in values]
                }
            }
        else:
            inner = {
                "bool": {"filter": [type_filter, {"terms": {values_path: values}}]}
            }

        return {"nested": {"path": nested_path, "query": inner}}
