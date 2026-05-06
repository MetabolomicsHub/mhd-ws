from mtbls_advanced_search.domain.plan import (
    IdCollectionStage,
    IdInSetConstraint,
    IdSetOutput,
    QueryPlan,
    QueryStage,
    SearchHitsOutput,
    SearchStage,
)

# Transitional aliases retained locally while mhd-ws callers move to the
# neutral shared-package stage vocabulary.
DatasetHitsOutput = SearchHitsOutput
DatasetIdConstraint = IdInSetConstraint
DatasetIdSetOutput = IdSetOutput
DatasetSearchStage = SearchStage
MetaboliteIdStage = IdCollectionStage

__all__ = [
    "DatasetHitsOutput",
    "DatasetIdConstraint",
    "DatasetIdSetOutput",
    "DatasetSearchStage",
    "IdCollectionStage",
    "IdInSetConstraint",
    "IdSetOutput",
    "MetaboliteIdStage",
    "QueryPlan",
    "QueryStage",
    "SearchHitsOutput",
    "SearchStage",
]
