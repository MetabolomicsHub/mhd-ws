import datetime
import enum
from logging import getLogger
from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import (
    APIRouter,
    Depends,
    Query,
    Response,
)
from fastapi import status as http_status
from pydantic import Field, field_serializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession

from mhd_ws.domain.shared.model import MhdBaseModel
from mhd_ws.infrastructure.persistence.db.db_client import DatabaseClient
from mhd_ws.infrastructure.persistence.db.mhd import (
    AccessionType,
    Dataset,
    DatasetStatus,
)
from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.db_utils import (
    create_new_identifier,
)
from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.dependencies import (
    RepositoryModel,
    validate_api_token,
)

logger = getLogger(__name__)

router = APIRouter(tags=["MHD Identifiers"], prefix="/v0_1")


class DatasetModel(MhdBaseModel):
    accession: Annotated[
        str,
        Field(
            title="MHD Identifier", description="Assigned MetabolomicsHub identifier"
        ),
    ]
    accession_type: Annotated[
        AccessionType,
        Field(
            title="Accession Type", description="Accession type. mhd, legacy, test, dev"
        ),
    ]
    created_at: Annotated[
        datetime.datetime, Field(title="Created Time", description="Created datetime")
    ]
    updated_at: Annotated[
        datetime.datetime | None,
        Field(title="Updated Time", description="Updated datetime"),
    ] = None
    revision: Annotated[
        None | int,
        Field(title="Revision Number", description="Revision number"),
    ] = None
    revision_datetime: Annotated[
        None | datetime.datetime,
        Field(title="Revision Datetime", description="Revision datetime"),
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


class AssignNewIdentifierResponse(MhdBaseModel):
    repository_name: str | None = None
    assignment: ExtendedRepositoryDataset | None = None
    message: str | None = None


class IdentifiersResponse(MhdBaseModel):
    repository_name: str | None = None
    identifiers: list[RepositoryDataset] = []
    message: str | None = None


repository_id_description = """
A unique dataset identifier created by repository.
(e.g., repository accession number, database id, dataset ticket id, etc.)
This unique identifier is meaningful only within the repository and
is used to define a one-to-one link between the repository dataset and MetabolomicsHub.
"""


class AccessionTypeQuery(enum.StrEnum):
    NONE = "-"
    MHD = "mhd"
    LEGACY = "legacy"
    TEST_MHD = "test-mhd"
    TEST_LEGACY = "test-legacy"
    DEV = "dev"


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
        Query(
            title="Repository identifier that links to the repository dataset.",
            description=repository_id_description,
        ),
    ],
    accession_type: Annotated[
        AccessionTypeQuery,
        Query(
            title="Accession type",
            description="Accession type.",
        ),
    ],
    db_client: None | DatabaseClient = Depends(Provide["gateways.database_client"]),
):
    if not repository:
        response.status_code = http_status.HTTP_403_FORBIDDEN
        return AssignNewIdentifierResponse(
            assignment=None, message="Unauthorized request."
        )

    if accession_type == AccessionTypeQuery.NONE:
        response.status_code = http_status.HTTP_400_BAD_REQUEST
        return AssignNewIdentifierResponse(
            assignment=None, message="Accession type is required."
        )
    selected_accession_type = AccessionType(accession_type.value)
    dataset, message = await create_new_identifier(
        db_client, selected_accession_type, repository, dataset_repository_identifier
    )
    if not dataset:
        response.status_code = http_status.HTTP_400_BAD_REQUEST
        return AssignNewIdentifierResponse(
            assignment=None, message=message or "Failed to create new MHD identifier."
        )
    return AssignNewIdentifierResponse(
        assignment=ExtendedRepositoryDataset(
            accession_type=dataset.accession_type,
            accession=dataset.accession,
            dataset_repository_identifier=dataset_repository_identifier,
            created_at=dataset.created_at,
            status=dataset.status,
            repository_name=repository.name,
            revision_number=dataset.revision,
            revision_datetime=dataset.revision_datetime,
        ),
        repository_name=repository.name,
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
    response: Response,
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
    accession_type: Annotated[
        list[AccessionType],
        Query(
            title="Accession type",
            description="Accession type.",
            min_length=1,
        ),
    ] = [AccessionType.MHD, AccessionType.LEGACY],
    status: Annotated[
        list[DatasetStatusQuery],
        Query(
            title="Dataset status.",
            description="Dataset status.",
            min_length=1,
        ),
    ] = [DatasetStatusQuery.PRIVATE, DatasetStatusQuery.PUBLIC],
    # cache_service: CacheService = Depends(Provide["services.cache_service"]),  # noqa: FAST002
    db_client: None | DatabaseClient = Depends(Provide["gateways.database_client"]),
):
    if not repository:
        response.status_code = http_status.HTTP_403_FORBIDDEN
        return IdentifiersResponse(
            message="Unauthorized request.",
            identifiers=[],
            repository_name=None,
        )

    query = select(Dataset).where(Dataset.repository_id == repository.id)
    where = []
    if accession:
        where.append(Dataset.accession == accession)

    if dataset_repository_identifier:
        where.append(
            Dataset.dataset_repository_identifier == dataset_repository_identifier
        )
    if accession_type:
        where.append(Dataset.accession_type.in_(accession_type))
    if status:
        where.append(Dataset.status.in_([DatasetStatus[x.value] for x in status]))

    if where:
        query = query.where(*where)

    stmt = query.order_by(Dataset.accession.asc())

    async with db_client.session() as a_session:
        session: AsyncSession = a_session
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
