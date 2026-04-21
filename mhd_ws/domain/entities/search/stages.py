from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

from mhd_ws.domain.entities.search.predicate_tree import BoolExpr


class DatasetIdSetOutput(BaseModel):
    type: Literal["DATASET_ID_SET"] = "DATASET_ID_SET"
    field_key: Literal["dataset_id"] = "dataset_id"
    max_ids: int = Field(default=50_000, ge=1)


class DatasetHitsOutput(BaseModel):
    type: Literal["DATASET_HITS"] = "DATASET_HITS"
    includes: Optional[list[str]] = None


class MetaboliteIdStage(BaseModel):
    id: Literal["stage_metabolite_ids"] = "stage_metabolite_ids"
    kind: Literal["METABOLITE_IDS"] = "METABOLITE_IDS"
    index_key: Literal["metabolite-index"] = "metabolite-index"

    metabolite_predicate: BoolExpr

    output: DatasetIdSetOutput = Field(default_factory=DatasetIdSetOutput)


class DatasetIdConstraint(BaseModel):
    kind: Literal["DATASET_ID_IN"] = "DATASET_ID_IN"
    from_stage_id: Literal["stage_metabolite_ids"] = "stage_metabolite_ids"


class DatasetSearchStage(BaseModel):
    id: Literal["stage_dataset_search"] = "stage_dataset_search"
    kind: Literal["DATASET_SEARCH"] = "DATASET_SEARCH"
    index_key: Literal["ms-dataset-index"] = "ms-dataset-index"
    dataset_predicate: BoolExpr
    constraints: list[DatasetIdConstraint] = Field(default_factory=list)
    output: DatasetHitsOutput = Field(default_factory=DatasetHitsOutput)


QueryStage = Annotated[
    Union[MetaboliteIdStage, DatasetSearchStage],
    Field(discriminator="kind"),
]


class QueryPlan(BaseModel):
    stages: Annotated[list[QueryStage], Field(min_length=1)]
    final_stage_id: Literal["stage_dataset_search"] = "stage_dataset_search"
