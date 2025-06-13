import datetime
import enum
from logging import getLogger
from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Header, Query, Response, status
from metabolights_utils.common import CamelCaseModel
from pydantic import BaseModel, Field, field_serializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mhd_ws.application.services.interfaces.cache_service import CacheService
from mhd_ws.infrastructure.persistence.db.mhd import (
    Dataset,
    DatasetStatus,
    Identifier,
    Repository,
)
from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.db import get_db
from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.dependencies import (
    RepositoryModel,
    validate_api_token,
)

logger = getLogger(__name__)

router = APIRouter(tags=["MHD Identifiers"], prefix="/v0_1")


class DatasetModel(CamelCaseModel):
    accession: Annotated[
        str,
        Field(
            title="MHD Identifier", description="Assigned MetabolomicsHub identifier"
        ),
    ]
    created_at: Annotated[
        datetime.datetime, Field(title="Created Time", description="Created datetime")
    ]
    updated_at: Annotated[
        datetime.datetime | None,
        Field(title="Updated Time", description="Updated datetime"),
    ] = None
    status: Annotated[
        DatasetStatus,
        Field(
            title="Dataset Access Level",
            description="Dataset access level. PRIVATE, PUBLIC, INVALID",
        ),
    ] = DatasetStatus.PRIVATE

    @field_serializer("status")
    @classmethod
    def hashes_serializer(cls, value):
        if value is None:
            return ""
        if isinstance(value, DatasetStatus):
            return value.name
        return value


class RepositoryDataset(DatasetModel):
    dataset_repository_identifier: Annotated[
        str,
        Field(
            title="Repository Dataset Identifier",
            description="Dataset identifier within repository",
        ),
    ]


class ExtendedRepositoryDataset(RepositoryDataset):
    repository_name: Annotated[
        None | str,
        Field(
            title="Repository Name",
            description="Repository name stored on MetabolomicsHub database.",
        ),
    ] = None


class AssignNewIdentifierResponse(BaseModel):
    repository_name: str | None = None
    assignment: ExtendedRepositoryDataset | None = None
    message: str | None = None


class IdentifiersResponse(BaseModel):
    repository_name: str | None = None
    identifiers: list[RepositoryDataset] = []
    message: str | None = None


repository_id_description = """
A unique dataset identifier created by repository. 
(e.g., repository accession number, database id, dataset ticket id, etc.)
This unique identifier is meaningful only within the repository and 
is used to define a one-to-one link between the repository dataset and MetabolomicsHub.
"""

accession_table_prefix = "mhd"
dataset_accession_prefix = "MHDA"


@router.post(
    "/identifiers",
    summary="Request New MetabolomicsHub (MHD) Identifier",
    description="Request new MetabolomicsHub (MHD) Identifier for a public or private dataset",
    response_model=AssignNewIdentifierResponse,
    responses={
        201: {
            "description": "New MHD identifier is created.",
        },
        401: {
            "description": "Unauthorized request.",
        },
    },
)
@inject
async def request_new_identifier(
    response: Response,
    repository: Annotated[None | RepositoryModel, Depends(validate_api_token)],
    dataset_repository_identifier: Annotated[
        str,
        Header(
            title="Repository identifier that links to the repository dataset.",
            description=repository_id_description,
            alias="x-dataset-repository-identifier",
        ),
    ],
    cache_service: CacheService = Depends(
        Provide["services.cache_service"]
    ),  # noqa: FAST002
    session: Annotated[AsyncSession, Depends(get_db)] = None,
):
    if not repository:
        response.status_code = status.HTTP_403_FORBIDDEN
        return {"message": "Unauthorized request."}
    async with session:
        stmt = select(Repository).where(Repository.id == repository.id).limit(1)
        result = await session.execute(stmt)
        db_repository = result.scalar_one_or_none()
        ref_id = dataset_repository_identifier
        query = select(Dataset)
        query = query.where(Dataset.dataset_repository_identifier == ref_id)
        query = query.where(Dataset.repository_id == repository.id)
        stmt = query.limit(1)

        result = await session.execute(stmt)
        current_dataset = result.scalar_one_or_none()
        if current_dataset is not None:
            response.status_code = status.HTTP_400_BAD_REQUEST
            session.rollback()

            return AssignNewIdentifierResponse(
                assignment=None,
                message=f"{repository.name} dataset with identifier {ref_id} already exists.",
            )

        try:
            dataset = Dataset(
                repository=db_repository,
                dataset_repository_identifier=dataset_repository_identifier,
                status=DatasetStatus.PRIVATE,
            )
            stmt = (
                select(Identifier)
                .where(Identifier.prefix == accession_table_prefix)
                .limit(1)
                .with_for_update()
            )
            result = await session.execute(stmt)
            last_accession = result.scalar_one_or_none()
            if not last_accession:
                await session.rollback()
                response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
                return AssignNewIdentifierResponse(
                    assignment=None, message="Failed to create new MHD identifier."
                )
            last_accession.last_identifier += 1
            dataset.accession = (
                f"{dataset_accession_prefix}{last_accession.last_identifier:06}"
            )
            session.add(dataset)
            await session.commit()
            await session.refresh(dataset)
            logger.info(
                "New MHD identifier %s created for %s.",
                dataset.accession,
                repository.name,
            )
            return AssignNewIdentifierResponse(
                assignment=ExtendedRepositoryDataset(
                    dataset_repository_identifier=dataset_repository_identifier,
                    accession=dataset.accession,
                    created_at=dataset.created_at,
                    status=dataset.status,
                    repository_name=repository.name,
                ),
                repository_name=repository.name,
            )

        except Exception as e:
            await session.rollback()
            logger.ex("Failed to create new MHD identifier: %s", str(e))
            return AssignNewIdentifierResponse(
                assignment=None, message="Failed to create new MHD identifier."
            )


class DatasetStatusQuery(enum.StrEnum):
    """Dataset status."""

    PRIVATE = DatasetStatus.PRIVATE.name
    PUBLIC = DatasetStatus.PUBLIC.name
    INVALID = DatasetStatus.INVALID.name


@router.get(
    "/identifiers",
    summary="Show Information About MHD Identifier",
    description="Show information about MHD identifier (e.g., created time, repostority, etc.).",
    response_model=IdentifiersResponse,
)
@inject
async def get_identifiers(
    repository: Annotated[None | RepositoryModel, Depends(validate_api_token)],
    accession: Annotated[
        None | str,
        Query(
            title="MHD identifier of the requested dataset.",
            description="MHD identifier of the requested dataset.",
        ),
    ] = None,
    dataset_repository_identifier: Annotated[
        None | str,
        Query(
            title="Repository identifier of the requested dataset.",
            description="Repository identifier of the requested dataset.",
        ),
    ] = None,
    status: Annotated[
        None | DatasetStatusQuery,
        Query(
            title="Dataset status.",
            description="Dataset status.",
        ),
    ] = None,
    cache_service: CacheService = Depends(
        Provide["services.cache_service"]
    ),  # noqa: FAST002
    session: Annotated[AsyncSession, Depends(get_db)] = None,
):
    query = select(Dataset).where(Dataset.repository_id == repository.id)
    if accession:
        query = query.where(Dataset.accession == accession)
    if dataset_repository_identifier:
        query = query.where(
            Dataset.dataset_repository_identifier == dataset_repository_identifier
        )
    if status:
        query = query.where(Dataset.status == DatasetStatus[status.value])

    stmt = query.order_by(Dataset.accession.asc())
    async with session:
        result = await session.execute(stmt)
        db_assignments = result.scalars().all()
        assignments = [
            RepositoryDataset.model_validate(x, from_attributes=True)
            for x in db_assignments
        ]
        if not assignments:
            return IdentifiersResponse(
                message="No dataset found.",
                identifiers=[],
                repository_name=repository.name,
            )
        message = f"{len(assignments)} repository datasets."
        if len(assignments) == 1:
            message = "1 repository dataset."

        return IdentifiersResponse(
            message=message,
            identifiers=assignments,
            repository_name=repository.name,
        )
