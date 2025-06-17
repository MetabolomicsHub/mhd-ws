import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, field_serializer, field_validator

from mhd_ws.infrastructure.persistence.db.mhd import DatasetRevisionStatus

T = TypeVar("T")


class DatasetRevisionError(Exception): ...


class TaskResult(BaseModel, Generic[T]):
    success: bool = False
    message: None | str = None
    result: None | T = None
    errors: None | dict[str, str] = None


class CreateDatasetRevisionModel(BaseModel):
    accession: None | str = None
    revision: None | int = None
    revision_datetime: datetime.datetime | None = None
    description: None | str = None
    repository_revision: int | None = None
    repository_revision_datetime: datetime.datetime | None = None
    status: None | DatasetRevisionStatus = None

    @field_validator("status", mode="before")
    @classmethod
    def status_validator(cls, value):
        if value is None:
            return DatasetRevisionStatus.INVALID
        if isinstance(value, int):
            return DatasetRevisionStatus(value)
        if isinstance(value, DatasetRevisionStatus):
            return value
        elif isinstance(value, str):
            return DatasetRevisionStatus[value]
        return DatasetRevisionStatus.INVALID

    @field_serializer("status")
    @classmethod
    def status_serializer(cls, value):
        if value is None:
            return ""
        if isinstance(value, DatasetRevisionStatus):
            return value.name
        return value


class FileValidationModel(BaseModel):
    task_id: str
    file: str | None = None
    repository_id: None | int
    repository_name: str
    schema_uri: str
    profile_uri: str
    mhd_identifier: str
    repository_identifier: str
    repository_revision: None | int = None
    repository_revision_datetime: None | str = None


class DatasetRevisionModel(BaseModel):
    id: int
    dataset_id: int
    revision: int
    revision_datetime: datetime.datetime | None = None
    task_id: str
    status: DatasetRevisionStatus
    description: str
    created_at: datetime.datetime | None = None
    file_id: int
    repository_revision: int | None = None
    repository_revision_datetime: str | None = None
    updated_at: datetime.datetime | None = None
