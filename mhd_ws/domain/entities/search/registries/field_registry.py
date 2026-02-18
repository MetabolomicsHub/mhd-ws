from mhd_ws.domain.entities.search.index_search_spec import Target, ValueType
from mhd_ws.domain.entities.search.registries.models import (
    AllowedOperators,
    FieldDef,
    FieldRegistry,
)

FIELD_REGISTRY = FieldRegistry(
    fields=[
        # --- join / identity ---
        FieldDef(
            field_id="dataset_id",
            field_key="dataset_id",
            target=Target.DATASET,
            value_type=ValueType.KEYWORD,
            ops=AllowedOperators(
                allow_terms=True,
                allow_comparators=False,
                allowed_match_modes=["EXACT"],
                allowed_intra_combiners=["OR"],
                allowed_comparators=["EQ"],
            ),
            description="Dataset identifier (canonical join key)",
        ),
        # --- dataset text-ish ---
        FieldDef(
            field_id="dataset_title",
            field_key="dataset.title",
            target=Target.DATASET,
            value_type=ValueType.TEXT,
            ops=AllowedOperators(
                allow_terms=True,
                allow_comparators=False,
                allowed_match_modes=["AUTO", "PHRASE", "EXACT"],
                allowed_intra_combiners=["AND", "OR"],
            ),
            description="Study/dataset title",
        ),
        FieldDef(
            field_id="dataset_description",
            field_key="dataset.description",
            target=Target.DATASET,
            value_type=ValueType.TEXT,
            ops=AllowedOperators(
                allow_terms=True,
                allow_comparators=False,
                allowed_match_modes=["AUTO", "PHRASE"],
                allowed_intra_combiners=["AND", "OR"],
            ),
            description="Study/dataset description",
        ),
        FieldDef(
            field_id="dataset_search_text",
            field_key="dataset.search_text",
            target=Target.DATASET,
            value_type=ValueType.TEXT,
            ops=AllowedOperators(
                allow_terms=True,
                allow_comparators=False,
                allowed_match_modes=["AUTO", "PHRASE"],
                allowed_intra_combiners=["AND", "OR"],
            ),
            description="Flattened dataset search_text",
        ),
        # --- dataset facets (keyword) ---
        FieldDef(
            field_id="facet_organisms",
            field_key="dataset.facets.organisms",
            target=Target.DATASET,
            value_type=ValueType.KEYWORD,
            ops=AllowedOperators(
                allow_terms=True,
                allow_comparators=False,
                allowed_match_modes=["EXACT"],
                allowed_intra_combiners=["AND", "OR"],
            ),
            description="Faceted organisms",
        ),
        FieldDef(
            field_id="facet_diseases",
            field_key="dataset.facets.diseases",
            target=Target.DATASET,
            value_type=ValueType.KEYWORD,
            ops=AllowedOperators(
                allow_terms=True,
                allow_comparators=False,
                allowed_match_modes=["EXACT"],
                allowed_intra_combiners=["AND", "OR"],
            ),
            description="Faceted diseases",
        ),
        FieldDef(
            field_id="facet_sample_types",
            field_key="dataset.facets.sample_types",
            target=Target.DATASET,
            value_type=ValueType.KEYWORD,
            ops=AllowedOperators(
                allow_terms=True,
                allow_comparators=False,
                allowed_match_modes=["EXACT"],
                allowed_intra_combiners=["AND", "OR"],
            ),
            description="Faceted sample types",
        ),
        # --- dataset nested person search ---
        FieldDef(
            field_id="person_name",
            field_key="dataset.people.full_name",
            target=Target.DATASET,
            value_type=ValueType.TEXT,
            ops=AllowedOperators(
                allow_terms=True,
                allow_comparators=False,
                allowed_match_modes=["AUTO", "PHRASE", "EXACT"],
                allowed_intra_combiners=["AND", "OR"],
            ),
            description="People.full_name (nested)",
        ),
        # --- metabolite fields ---
        FieldDef(
            field_id="metabolite_name",
            field_key="metabolite.name",
            target=Target.METABOLITE,
            value_type=ValueType.TEXT,
            ops=AllowedOperators(
                allow_terms=True,
                allow_comparators=False,
                allowed_match_modes=["AUTO", "PHRASE", "EXACT"],
                allowed_intra_combiners=["AND", "OR"],
            ),
            description="Metabolite name",
        ),
        FieldDef(
            field_id="metabolite_accession",
            field_key="metabolite.accession",
            target=Target.METABOLITE,
            value_type=ValueType.KEYWORD,
            ops=AllowedOperators(
                allow_terms=True,
                allow_comparators=False,
                allowed_match_modes=["EXACT"],
                allowed_intra_combiners=["AND", "OR"],
            ),
            description="Metabolite accession",
        ),
        # --- metabolite identifiers (nested) ---
        FieldDef(
            field_id="metabolite_identifier_accession",
            field_key="metabolite.identifiers.accession",
            target=Target.METABOLITE,
            value_type=ValueType.KEYWORD,
            ops=AllowedOperators(
                allow_terms=True,
                allow_comparators=False,
                allowed_match_modes=["EXACT"],
                allowed_intra_combiners=["AND", "OR"],
            ),
            description="Metabolite identifiers.accession (nested)",
        ),
        FieldDef(
            field_id="metabolite_identifier_name",
            field_key="metabolite.identifiers.name",
            target=Target.METABOLITE,
            value_type=ValueType.KEYWORD,
            ops=AllowedOperators(
                allow_terms=True,
                allow_comparators=False,
                allowed_match_modes=["EXACT"],
                allowed_intra_combiners=["AND", "OR"],
            ),
            description="Metabolite identifiers.name (nested)",
        ),
        FieldDef(
            field_id="metabolite_identifier_source",
            field_key="metabolite.identifiers.source",
            target=Target.METABOLITE,
            value_type=ValueType.KEYWORD,
            ops=AllowedOperators(
                allow_terms=True,
                allow_comparators=False,
                allowed_match_modes=["EXACT"],
                allowed_intra_combiners=["AND", "OR"],
            ),
            description="Metabolite identifiers.source (nested)",
        ),
    ]
)
