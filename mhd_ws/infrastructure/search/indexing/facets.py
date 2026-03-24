"""Facet configuration and routing helpers."""

from __future__ import annotations

ASSAY_FACET_REF_KEYS: tuple[tuple[str, str], ...] = (
    ("technology_types", "technology_type_ref"),
    ("assay_types", "assay_type_ref"),
    ("measurement_types", "measurement_type_ref"),
    ("omics_types", "omics_type_ref"),
)

FACET_KEYS: tuple[str, ...] = (
    "organisms",
    "organism_accessions",
    "diseases",
    "disease_accessions",
    "tissues",
    "sample_types",
    "characteristic_types",
    "omics_types",
    "measurement_types",
    "assay_types",
    "technology_types",
    # ms profile additions
    "protocol_types",
    "parameter_types",
    "parameter_values",
    "parameter_kv",
)

SEARCH_FACET_KEYS: tuple[str, ...] = (
    "characteristic_types",
    "omics_types",
    "measurement_types",
    "assay_types",
    "technology_types",
    "organisms",
    "diseases",
    "tissues",
    "sample_types",
)

CHARACTERISTIC_TYPE_TO_FACET: dict[str, str] = {
    "organism": "organisms",
    "species": "organisms",
    "organism part": "tissues",
    "tissue": "tissues",
    "tissues": "tissues",
    "disease": "diseases",
    "phenotype": "diseases",
    "sample type": "sample_types",
    "specimen": "sample_types",
}


def route_characteristic_to_facet(char_type_name: str) -> str | None:
    """Map a characteristic type name to a facet bucket."""
    name = (char_type_name or "").strip().lower()
    if not name:
        return None
    return CHARACTERISTIC_TYPE_TO_FACET.get(name)
