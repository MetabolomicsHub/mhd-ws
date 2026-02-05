import datetime
import enum
import hashlib
import json
import uuid
from logging import getLogger
from typing import Annotated, Any

from dependency_injector.wiring import Provide, inject
from fastapi import (
    APIRouter,
    Depends,
    File,
    Header,
    Path,
    Query,
    Response,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from pydantic import Field, PositiveInt
from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession
from sqlalchemy.sql import or_
from starlette import status as http_status

from mhd_ws.application.services.interfaces.async_task.async_task_service import (
    AsyncTaskService,
    IdGenerator,
)
from mhd_ws.application.services.interfaces.cache_service import CacheService
from mhd_ws.domain.shared.model import MhdBaseModel
from mhd_ws.infrastructure.persistence.db.db_client import DatabaseClient
from mhd_ws.infrastructure.persistence.db.mhd import (
    AccessionType,
    AnnouncementFile,
    Dataset,
    DatasetRevision,
)
from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.db_utils import (
    create_new_identifier,
)
from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.dependencies import (
    RepositoryModel,
    validate_api_token,
)
from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.models import (
    CreateDatasetRevisionModel,
    FileValidationModel,
    TaskResult,
)
from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.tasks import (
    add_submission_task,
    announcement_file_validation_task,
    common_dataset_file_validation_task,
)

logger = getLogger(__name__)

router = APIRouter(prefix="/v0_1")


class TaskStatus(enum.StrEnum):
    INITIATED = "INITIATED"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class MhdAsyncTaskResponse(MhdBaseModel):
    accession: Annotated[
        None | str,
        Field(
            title="MHD Identifier", description="Assigned MetabolomicsHub identifier"
        ),
    ] = None
    dataset_repository_identifier: Annotated[
        None | str,
        Field(
            title="Repository Dataset Identifier",
            description="Assigned Repository Dataset identifier",
        ),
    ] = None
    task_id: Annotated[
        None | str,
        Field(
            title="Submission Task Id",
            description="MetabolomicsHub submission task id",
        ),
    ] = None
    task_status: Annotated[
        None | TaskStatus, Field(title="Task Status", description="Task status")
    ] = None
    messages: Annotated[
        list[str] | None, Field(title="Messages", description="Announcement messages")
    ] = None
    created_at: Annotated[
        None | datetime.datetime,
        Field(title="Created At", description="Created datetime"),
    ] = None
    updated_at: Annotated[
        datetime.datetime | None,
        Field(title="Updated At", description="Updated datetime"),
    ] = None
    errors: Annotated[
        None | list[str] | dict[str, str],
        Field(title="Errors", description="MetabolomicsHub submission task errors"),
    ] = None
    result: Annotated[
        None | CreateDatasetRevisionModel | FileValidationModel,
        Field(title="Task result", description="Task result"),
    ] = None


class Revision(MhdBaseModel):
    accession: Annotated[
        str,
        Field(
            title="MHD Identifier", description="Assigned MetabolomicsHub identifier"
        ),
    ]
    repository: Annotated[
        str, Field(title="Repository Name", description="Repository name")
    ]
    revision_number: Annotated[
        int, Field(title="Revision number", description="Revision number")
    ]
    announcement_datetime: Annotated[
        datetime.datetime,
        Field(
            title="Announcement Datetime", description="Revision announcement datetime"
        ),
    ]
    revision_comment: Annotated[
        int, Field(title="Revision Comment", description="Revision comment")
    ]


class MhDatasetRevision(MhdBaseModel):
    revision_number: Annotated[
        int, Field(title="Revision number", description="Revision number")
    ]
    revision_comment: Annotated[
        None | str, Field(title="Revision Comment", description="Revision comment")
    ] = None
    announcement_datetime: Annotated[
        datetime.datetime,
        Field(
            title="Announcement Datetime", description="Revision announcement datetime"
        ),
    ]


class MhDatasetRevisions(MhdBaseModel):
    accession: Annotated[
        str,
        Field(
            title="MHD Identifier", description="Assigned MetabolomicsHub identifier"
        ),
    ]
    repository: Annotated[
        str, Field(title="Repository Name", description="Repository name")
    ]
    revisions: Annotated[
        None | list[MhDatasetRevision],
        Field(title="Dataset revisions", description="Dataset revisions"),
    ] = None
    errors: Annotated[
        None | list[str],
        Field(title="Errors", description="Errors"),
    ] = None


class RevisionSelection(enum.StrEnum):
    ALL = "all"
    LATEST = "latest"
    SELECTED = "selected"


@router.post(
    "/datasets/{accession}/announcements",
    summary="Announce New Dataset Revision",
    description="""
Announce new dataset revision. First public revision is 1.
If there is any (meta)data update on repository, repository should announce new dataset revision.
After first successful announcement, dataset access level will be public.
""",
    tags=["Dataset Announcements"],
    response_model=MhdAsyncTaskResponse,
    responses={
        200: {
            "description": "MHD Async Task",
            "content": {
                "application/json": {
                    "example": MhdAsyncTaskResponse(
                        accession="MHD000001",
                        task_id="create-revision-23a08167-89e8-4e28-a824-38c66f92f437",
                        task_status=TaskStatus.INITIATED,
                        messages=["Task is initiated"],
                        created_at=datetime.datetime(2020, 1, 30),
                        updated_at=None,
                    ).model_dump(by_alias=True)
                }
            },
        },
        400: {
            "description": "Bad Request.",
        },
        401: {
            "description": "Unauthorized.",
        },
        403: {
            "description": "Forbidden request.",
        },
        404: {
            "description": "Not Found.",
        },
    },
)
@inject
async def make_new_announcement(
    response: Response,
    accession: Annotated[
        str,
        Path(
            title="MHD Identifier or Repository Dataset Identifier",
            description="MHD Identifier for MetabolomicsHub datasets. "
            "Use dataset repository identifier for legacy datasets.",
        ),
    ],
    announcement_reason: Annotated[
        None | str,
        Header(
            title="Announcement reason. ",
            description="Announcement reason. Example: 'Initial revision', 'Update publication DOI', 'Update sample metadata', etc",
            alias="x-announcement-reason",
            min_length=1,
        ),
    ],
    file: Annotated[
        UploadFile,
        File(
            title="MetabolomicsHub Dataset Announcement File",
            description="MetabolomicsHub Dataset Announcement File.",
        ),
    ],
    cache_service: CacheService = Depends(Provide["services.cache_service"]),  # noqa: FAST002
    db_client: None | DatabaseClient = Depends(Provide["gateways.database_client"]),
    async_task_service: AsyncTaskService = Depends(  # noqa: FAST002
        Provide["services.async_task_service"]
    ),
    repository: Annotated[None | RepositoryModel, Depends(validate_api_token)] = None,
):
    if not accession:
        response.status_code = http_status.HTTP_400_BAD_REQUEST
        error = "accession is required."
        logger.error(error)
        return MhdAsyncTaskResponse(accession=accession, errors=[error])
    if not repository:
        response.status_code = http_status.HTTP_401_UNAUTHORIZED
        error = "Repository token is not valid"
        return MhdAsyncTaskResponse(accession=accession, errors=[error])
    accession_type = None
    dataset: None | Dataset = None
    async with db_client.session() as session:
        where = [Dataset.repository_id == repository.id]
        where.append(
            or_(
                Dataset.dataset_repository_identifier == accession,
                Dataset.accession == accession,
            )
        )

        stmt = select(Dataset).where(*where)
        result = await session.execute(stmt)
        dataset: Dataset | None = result.scalar()
        accession_type = dataset.accession_type if dataset else None

    file_cache_key = f"new-announcement:{accession}"
    task_id = await cache_service.get_value(file_cache_key)
    if task_id is not None:
        error = f"Task id {task_id} already exists for {accession}."
        logger.error(error)
        response.status_code = http_status.HTTP_425_TOO_EARLY
        return MhdAsyncTaskResponse(task_id=task_id, errors=[error])
    contents = await file.read()
    try:
        announcement_file_json = json.loads(contents.decode())
        profile_uri = announcement_file_json.get("profile_uri", "")
        legacy_profile = profile_uri.endswith(
            "legacy-profile.json"
        ) or not accession.startswith("MHD")

        mhd_identifier = announcement_file_json.get("mhd_identifier", None)
        dataset_repository_identifier = announcement_file_json.get(
            "repository_identifier", None
        )
        if not dataset_repository_identifier:
            response.status_code = http_status.HTTP_400_BAD_REQUEST
            error = "Repository identifier is required in the announcement file."
            logger.error(error)
            return MhdAsyncTaskResponse(accession=accession, errors=[error])
        if legacy_profile:
            if (
                accession_type in (AccessionType.TEST_LEGACY, AccessionType.LEGACY)
                and dataset_repository_identifier != accession
                and dataset_repository_identifier != mhd_identifier
            ):
                response.status_code = http_status.HTTP_400_BAD_REQUEST
                error = (
                    "Repository identifier in the announcement file "
                    f"({dataset_repository_identifier}) does not match the input accession ({accession})."
                )
                logger.error(error)
                return MhdAsyncTaskResponse(accession=accession, errors=[error])

            if not dataset:
                dataset, message = await create_new_identifier(
                    db_client,
                    accession_type,
                    repository,
                    dataset_repository_identifier,
                )
                if not dataset:
                    response.status_code = http_status.HTTP_400_BAD_REQUEST
                    error = "Failed to create new dataset."
                    logger.error(error)
                    return MhdAsyncTaskResponse(accession=accession, errors=[error])

        if not dataset:
            response.status_code = http_status.HTTP_404_NOT_FOUND
            error = "No dataset found."
            logger.error(error)
            return MhdAsyncTaskResponse(accession=accession, errors=[error])

        if dataset.repository_id != repository.id:
            response.status_code = http_status.HTTP_403_FORBIDDEN
            error = "Repository has no permission to update dataset."
            return MhdAsyncTaskResponse(accession=accession, errors=[error])

    except json.JSONDecodeError:
        response.status_code = http_status.HTTP_400_BAD_REQUEST
        error = "Invalid JSON format in the announcement file."
        logger.error(error)
        return MhdAsyncTaskResponse(accession=accession, errors=[error])

    task_id = str(uuid.uuid4())
    await cache_service.set_value(
        file_cache_key,
        task_id,
        expiration_time_in_seconds=10 * 60,
    )

    executor = await async_task_service.get_async_task(
        add_submission_task,
        repository_id=repository.id,
        dataset_repository_identifier=dataset_repository_identifier,
        accession=accession,
        announcement_file_json=announcement_file_json,
        announcement_reason=announcement_reason,
        task_id=task_id,
        id_generator=IdGenerator(lambda: task_id),
    )

    result = await executor.start()
    task_id = result.get_id()
    logger.info("New revision task started for %s with task id %s", accession, task_id)

    try:
        updated_task_result = await async_task_service.get_async_task_result(task_id)
    except Exception:
        message = f"Current new revision task failed to start: {task_id}"
        logger.error(message)
        # await cache_service.delete_key(key)
        # raise AsyncTaskStartFailure(resource_id, task_id, message) from ex
        MhdAsyncTaskResponse(
            accession=accession,
            task_id=task_id,
            task_status="FAILED",
            messages=["Task failed."],
            created_at=datetime.datetime.now(datetime.UTC),
            updated_at=None,
        )

    if updated_task_result.get_status().upper().startswith("FAIL"):
        logger.error(
            "Current task id:'%s' and its status: %s.",
            updated_task_result.get_id(),
            updated_task_result.get_status(),
        )
    else:
        logger.debug(
            "Current task id:'%s' and its status: %s.",
            updated_task_result.get_id(),
            updated_task_result.get_status(),
        )
    return MhdAsyncTaskResponse(
        accession=accession,
        task_id=updated_task_result.get_id(),
        task_status=updated_task_result.get_status(),
        messages=["Task is submitted"],
        created_at=datetime.datetime.now(datetime.UTC),
        updated_at=None,
    )


@router.get(
    "/datasets/{accession}/tasks/{task_id}",
    summary="Check Result of Any Dataset Revision Async Task",
    description="Check result of any dataset revision task (new announcement, delete dataset, delete revision, etc.).",
    tags=["Dataset Announcements"],
    response_model=MhdAsyncTaskResponse,
    responses={
        200: {
            "description": "MHD Async Task",
            "content": {
                "application/json": {
                    "example": MhdAsyncTaskResponse(
                        accession="MHD000001",
                        task_id="create-revision-23a08167-89e8-4e28-a824-38c66f92f437",
                        task_status=TaskStatus.SUCCESS,
                        messages=["Task is completed"],
                        created_at=datetime.datetime(2020, 1, 30),
                        updated_at=datetime.datetime(2020, 3, 30),
                    ).model_dump(by_alias=True)
                }
            },
        },
        400: {
            "description": "Bad Request.",
        },
        401: {
            "description": "Unauthorized.",
        },
        403: {
            "description": "Forbidden request.",
        },
        404: {
            "description": "Not Found.",
        },
    },
)
@inject
async def get_task_status(
    response: Response,
    accession: Annotated[
        str,
        Path(
            title="MHD Identifier",
            description="MHD Identifier.",
        ),
    ],
    task_id: Annotated[str, Path(title="Task id. ", description="task id.")],
    cache_service: CacheService = Depends(Provide["services.cache_service"]),  # noqa: FAST002
    async_task_service: AsyncTaskService = Depends(  # noqa: FAST002
        Provide["services.async_task_service"]
    ),
    repository: Annotated[None | RepositoryModel, Depends(validate_api_token)] = None,
):
    if not repository:
        response.status_code = http_status.HTTP_400_BAD_REQUEST
        return MhdAsyncTaskResponse(errors=["Invalid API token"])
    task_result = None
    try:
        task_result = await async_task_service.get_async_task_result(task_id)
        if not task_result.is_ready():
            file_cache_key = f"new-announcement:{accession}"
            cached_task_id = await cache_service.get_value(file_cache_key)
            if cached_task_id:
                return MhdAsyncTaskResponse(
                    accession=accession,
                    task_id=task_result.get_id(),
                    task_status=TaskStatus(task_result.get_status()),
                    messages=["Task is not completed yet."],
                )
            response.status_code = http_status.HTTP_404_NOT_FOUND
            return MhdAsyncTaskResponse(
                accession=accession, errors=[f"There is no task {task_id}."]
            )
        try:
            # if task_result.is_successful():
            result = task_result.get()
            output = TaskResult[CreateDatasetRevisionModel].model_validate(result)
            if output.success:
                return MhdAsyncTaskResponse(
                    accession=accession,
                    task_id=task_result.get_id(),
                    task_status=TaskStatus(task_result.get_status()),
                    result=output.result,
                    errors=output.errors,
                )
            return MhdAsyncTaskResponse(
                accession=accession,
                task_id=task_result.get_id(),
                task_status=TaskStatus.FAILED,
                messages=[output.message],
                errors=output.errors,
            )
        except Exception as ex:
            response.status_code = http_status.HTTP_400_BAD_REQUEST

            return MhdAsyncTaskResponse(
                accession=accession,
                task_id=task_result.get_id(),
                task_status=TaskStatus.FAILED,
                errors=[str(ex)],
            )
        finally:
            if task_result:
                task_result.revoke()

    except Exception as ex:
        message = f"Current validation task failed to start: {task_id}"
        logger.error(message)
        return MhdAsyncTaskResponse(
            accession=accession, task_status=TaskStatus.FAILED, errors=[str(ex)]
        )


@router.get(
    "/datasets/{accession}/announcements",
    summary="Get List of Dataset Revisions",
    description="Get list of dataset revisions.",
    tags=["Dataset Announcements"],
    response_model=MhDatasetRevisions,
    responses={
        200: {
            "description": "Revision List",
        },
        400: {
            "description": "Bad Request.",
        },
        401: {
            "description": "Unauthorized.",
        },
        403: {
            "description": "Forbidden request.",
        },
        404: {
            "description": "Not Found.",
        },
    },
)
@inject
async def get_revisions(
    response: Response,
    accession: Annotated[
        str,
        Path(
            title="MHD Identifier",
            description="MHD Identifier.",
        ),
    ],
    selection_type: Annotated[
        RevisionSelection,
        Query(
            title="Revision selection type.",
            description="selection type.",
        ),
    ] = RevisionSelection.LATEST,
    mhd_revision: Annotated[
        None | PositiveInt,
        Query(
            title="The selected revision only.",
            description="The selected revision only.",
        ),
    ] = None,
    repository: Annotated[None | RepositoryModel, Depends(validate_api_token)] = None,
    db_client: None | DatabaseClient = Depends(Provide["gateways.database_client"]),
    # cache_service: CacheService = Depends(Provide["services.cache_service"]),  # noqa: FAST002
):
    if not repository:
        response.status_code = http_status.HTTP_401_UNAUTHORIZED
        error = "Unauthorized request."
        return MhDatasetRevisions(
            accession=accession,
            repository=repository.name,
            errors=[error],
        )
    if selection_type == RevisionSelection.SELECTED and (
        not mhd_revision or mhd_revision < 1
    ):
        response.status_code = http_status.HTTP_400_BAD_REQUEST
        error = "Revision must be greater than 0."
        return MhDatasetRevisions(
            accession=accession,
            repository=repository.name,
            errors=[error],
        )

    async with db_client.session() as a_session:
        session: AsyncSession = a_session
        where_clauses = [
            Dataset.accession == accession,
            Dataset.repository_id == repository.id,
        ]
        query = select(DatasetRevision).join(
            Dataset,
            DatasetRevision.dataset_id == Dataset.id,
        )

        if selection_type == RevisionSelection.LATEST:
            where_clauses.append(DatasetRevision.revision == Dataset.revision)
        elif selection_type == RevisionSelection.SELECTED:
            where_clauses.append(DatasetRevision.revision == mhd_revision)
        query = query.where(*where_clauses).order_by(DatasetRevision.revision.desc())

        result = await session.execute(query)
        dataset_revisions: None | list[DatasetRevision] = result.scalars().all()

        if not dataset_revisions:
            response.status_code = http_status.HTTP_404_NOT_FOUND
            return MhDatasetRevisions(
                accession=accession,
                repository=repository.name,
                errors=[f"Dataset revision is not found for {accession}."],
            )
        revisions = [
            MhDatasetRevision(
                revision_number=x.revision,
                revision_comment=x.description,
                announcement_datetime=x.revision_datetime,
            )
            for x in dataset_revisions
        ]
        return MhDatasetRevisions(
            accession=accession,
            repository=repository.name,
            revisions=revisions,
        )


@router.get(
    "/datasets/{accession}/announcement-file",
    summary="Get List of Dataset Revisions",
    description="Get list of dataset revisions.",
    tags=["Dataset Announcements"],
    responses={
        200: {
            "description": "Revision List",
        },
        400: {
            "description": "Bad Request.",
        },
        401: {
            "description": "Unauthorized.",
        },
        403: {
            "description": "Forbidden request.",
        },
        404: {
            "description": "Not Found.",
        },
    },
)
@inject
async def get_revision_file(
    response: Response,
    accession: Annotated[
        str,
        Path(
            title="MHD Identifier or Dataset Repository Identifier",
            description="MHD Identifier for MetabolomicsHub datasets. "
            "Use dataset repository identifier for legacy datasets.",
        ),
    ],
    mhd_revision: Annotated[
        None | int,
        Query(
            title="The selected MetabolomicsHub revision.",
            description="The selected MetabolomicsHub revision. "
            "If not provided, the latest revision is returned.",
        ),
    ] = None,
    repository: Annotated[None | RepositoryModel, Depends(validate_api_token)] = None,
    db_client: None | DatabaseClient = Depends(Provide["gateways.database_client"]),
    # cache_service: CacheService = Depends(Provide["services.cache_service"]),  # noqa: FAST002
):
    if mhd_revision and mhd_revision < 1:
        response.status_code = http_status.HTTP_400_BAD_REQUEST
        error = "Revision must be greater than 0."
        return MhDatasetRevisions(
            accession=accession,
            repository=repository.name,
            errors=[error],
        )
    if not repository:
        response.status_code = http_status.HTTP_400_BAD_REQUEST
        error = "Repository is not found."
        return MhDatasetRevisions(
            accession=accession,
            repository=repository.name,
            errors=[error],
        )
    async with db_client.session() as session:
        query = (
            select(AnnouncementFile.file, DatasetRevision.revision)
            .join(
                DatasetRevision,
                DatasetRevision.file_id == AnnouncementFile.id,
            )
            .join(
                Dataset,
                DatasetRevision.dataset_id == Dataset.id,
            )
            .where(
                Dataset.accession == accession,
                Dataset.repository_id == repository.id,
            )
        )
        if mhd_revision:
            query = query.where(DatasetRevision.revision == mhd_revision)
        else:
            query = query.where(DatasetRevision.revision == Dataset.revision)

        result = await session.execute(query)
        result_tuple: None | tuple[dict[str, Any], int] = result.one_or_none()

        if not result_tuple:
            response.status_code = http_status.HTTP_404_NOT_FOUND
            error = (
                "Dataset announcement file is not defined "
                f"or selected revision {mhd_revision or ''} is not found."
            )
            return MhDatasetRevisions(
                accession=accession,
                repository=repository.name,
                errors=[error],
            )
        announcement_file, revision = result_tuple
        content = json.dumps(announcement_file, indent=2)
        download_filename = (
            f'attachment; filename="{accession}_announcement_rev_{revision:02}.json"'
        )
        headers = {
            "x-mtbls-file-type": "application/json",
            "Content-Disposition": download_filename,
        }
        report_chunk_size_in_bytes = 1024 * 1024 * 1

        def iter_content(data: str):
            for i in range(0, len(data), report_chunk_size_in_bytes):
                yield data[i : (i + report_chunk_size_in_bytes)]

        response = StreamingResponse(content=iter_content(content), headers=headers)
        return response


@router.delete(
    "/datasets/{accession}/announcements",
    summary="Delete All Dataset Revisions",
    description="""
Delete dataset and make it private
""",
    tags=["Dataset Announcements [Maintenance]"],
    response_model=MhdAsyncTaskResponse,
    include_in_schema=False,
    responses={
        200: {
            "description": "MHD Async Task",
            "content": {
                "application/json": {
                    "example": MhdAsyncTaskResponse(
                        accession="MHD000001",
                        task_id="delete-revisions-d3a08167-89e8-4e28-a824-38c66f92f437",
                        task_status=TaskStatus.INITIATED,
                        messages=["Task is initiated"],
                        created_at=datetime.datetime(2020, 1, 30),
                        updated_at=None,
                    ).model_dump(by_alias=True)
                }
            },
        },
        400: {
            "description": "Bad Request.",
        },
        401: {
            "description": "Unauthorized.",
        },
        403: {
            "description": "Forbidden request.",
        },
        404: {
            "description": "Not Found.",
        },
    },
)
@inject
async def delete_dataset(
    api_token: Annotated[
        str,
        Header(
            title="API token.",
            description="API token",
            alias="x-api-token",
        ),
    ],
    accession: Annotated[
        str,
        Path(
            title="MHD Identifier.",
            description="MHD Identifier.",
        ),
    ],
    cache_service: CacheService = Depends(Provide["services.cache_service"]),  # noqa: FAST002
):
    return MhdAsyncTaskResponse(
        accession="MHD000001",
        task_id="delete-revisions-d3a08167-89e8-4e28-a824-38c66f92f437",
        task_status=TaskStatus.SUCCESS,
        messages=["Task is completed"],
        created_at=datetime.datetime(2020, 1, 30),
        updated_at=None,
    )


@router.put(
    "/datasets/{accession}/announcements/{revision_number}",
    summary="Update Dataset Revision",
    description="""
Update dataset revision. Only latest dataset revision can be updated.
""",
    tags=["Dataset Announcements [Maintenance]"],
    response_model=MhdAsyncTaskResponse,
    include_in_schema=False,
    responses={
        200: {
            "description": "MHD Async Task",
            "content": {
                "application/json": {
                    "example": MhdAsyncTaskResponse(
                        accession="MHD000001",
                        task_id="update-revision-a3a08167-89e8-4e28-a824-38c66f92f437",
                        task_status=TaskStatus.INITIATED,
                        messages=["Task is initiated"],
                        created_at=datetime.datetime(2020, 1, 30),
                        updated_at=None,
                    ).model_dump(by_alias=True)
                }
            },
        },
        400: {
            "description": "Bad Request.",
        },
        401: {
            "description": "Unauthorized.",
        },
        403: {
            "description": "Forbidden request.",
        },
        404: {
            "description": "Not Found.",
        },
    },
)
@inject
async def update_dataset_revision(
    api_token: Annotated[
        str,
        Header(
            title="API token.",
            description="API token",
            alias="x-api-token",
        ),
    ],
    accession: Annotated[
        str,
        Path(
            title="MHD Identifier.",
            description="MHD Identifier.",
        ),
    ],
    revision_number: Annotated[
        int,
        Path(
            title="Revision number",
            description="Revision number",
        ),
    ],
    file: Annotated[
        UploadFile,
        File(
            title="MetabolomicsHub Dataset Announcement File",
            description="MetabolomicsHub Dataset Announcement File.",
        ),
    ],
    cache_service: CacheService = Depends(Provide["services.cache_service"]),  # noqa: FAST002
):
    return MhdAsyncTaskResponse(
        accession="MHD000001",
        task_id="delete-revisions-d3a08167-89e8-4e28-a824-38c66f92f437",
        task_status=TaskStatus.SUCCESS,
        messages=["Task is completed"],
        created_at=datetime.datetime(2020, 1, 30),
        updated_at=None,
    )


@router.delete(
    "/datasets/{accession}/announcements/{revision_number}",
    summary="Delete Dataset Revision",
    description="""
Delete dataset revision. Only the latest revision can be deleted.
""",
    tags=["Dataset Announcements [Maintenance]"],
    response_model=MhdAsyncTaskResponse,
    include_in_schema=False,
    responses={
        200: {
            "description": "MHD Async Task",
            "content": {
                "application/json": {
                    "example": MhdAsyncTaskResponse(
                        accession="MHD000001",
                        task_id="delete-revision-13a08167-89e8-4e28-a824-38c66f92f437",
                        task_status=TaskStatus.INITIATED,
                        messages=["Task is initiated"],
                        created_at=datetime.datetime(2020, 1, 30),
                        updated_at=None,
                    ).model_dump(by_alias=True)
                }
            },
        },
        400: {
            "description": "Bad Request.",
        },
        401: {
            "description": "Unauthorized.",
        },
        403: {
            "description": "Forbidden request.",
        },
        404: {
            "description": "Not Found.",
        },
    },
)
@inject
async def delete_dataset_revision(
    api_token: Annotated[
        str,
        Header(
            title="API token.",
            description="API token",
            alias="x-api-token",
        ),
    ],
    accession: Annotated[
        str,
        Path(
            title="MHD Identifier.",
            description="MHD Identifier.",
        ),
    ],
    revision_number: Annotated[
        int,
        Path(
            title="Revision number",
            description="Revision number",
        ),
    ],
    cache_service: CacheService = Depends(Provide["services.cache_service"]),  # noqa: FAST002
):
    # now = datetime.datetime.now(datetime.UTC)
    return MhdAsyncTaskResponse(
        accession="MHD000001",
        task_id="delete-revisions-d3a08167-89e8-4e28-a824-38c66f92f437",
        task_status=TaskStatus.INITIATED,
        messages=["Task is initiated."],
        created_at=datetime.datetime(2020, 1, 30),
        updated_at=None,
    )


@router.post(
    "/validations/announcement-file",
    summary="Validate Dataset Announcement File",
    description="Validate Dataset Announcement File and return validation results.",
    tags=["Dataset Validation"],
    response_model=MhdAsyncTaskResponse,
)
@inject
async def make_new_announcement_validation(
    response: Response,
    file: Annotated[
        UploadFile,
        File(
            title="MetabolomicsHub Dataset Announcement File",
            description="MetabolomicsHub Dataset Announcement File.",
        ),
    ],
    cache_service: CacheService = Depends(Provide["services.cache_service"]),  # noqa: FAST002
    async_task_service: AsyncTaskService = Depends(  # noqa: FAST002
        Provide["services.async_task_service"]
    ),
    repository: Annotated[None | RepositoryModel, Depends(validate_api_token)] = None,
):
    if not repository:
        response.status_code = http_status.HTTP_403_FORBIDDEN
        error = "API token is not valid"
        return MhdAsyncTaskResponse(
            errors=[error],
        )

    contents = await file.read()

    file_sha256 = hashlib.sha256(contents).hexdigest()

    file_cache_key = f"new-file-validation-task:{repository.id}:{file_sha256}"
    await cache_service.delete_key(file_cache_key)

    task_id = await cache_service.get_value(file_cache_key)
    if task_id is not None:
        error = "There is a task running for the current announcement file."
        logger.error(error)
        response.status_code = http_status.HTTP_425_TOO_EARLY
        return MhdAsyncTaskResponse(
            task_id=task_id,
            errors=[error],
        )
    task_id = str(uuid.uuid4())

    task_key = f"new-file-validation-task:{repository.id}:{task_id}"
    message = None
    await cache_service.set_value(
        file_cache_key,
        task_id,
        expiration_time_in_seconds=10 * 60,
    )

    await cache_service.set_value(
        task_key,
        file_sha256,
        expiration_time_in_seconds=10 * 60,
    )

    announcement_file_json = json.loads(contents.decode())
    executor = await async_task_service.get_async_task(
        announcement_file_validation_task,
        repository_id=repository.id,
        filename=file.filename,
        announcement_file_json=announcement_file_json,
        task_id=task_id,
        id_generator=IdGenerator(lambda: task_id),
    )

    result = await executor.start()
    task_id = result.get_id()
    logger.info(
        "New announcement file validation task started for the task %s", task_id
    )

    try:
        updated_task_result = await async_task_service.get_async_task_result(task_id)
    except Exception:
        message = (
            f"Current new announcement file validation task failed to start: {task_id}"
        )
        logger.error(message)
        # await cache_service.delete_key(key)
        # raise AsyncTaskStartFailure(resource_id, task_id, message) from ex
        return MhdAsyncTaskResponse(
            task_id=task_id,
            task_status=TaskStatus.FAILED,
            messages=["Task failed."],
            created_at=datetime.datetime.now(datetime.UTC),
            updated_at=None,
        )

    if updated_task_result.get_status().upper().startswith("FAIL"):
        logger.error(
            "Current task id:'%s' and its status: %s.",
            updated_task_result.get_id(),
            updated_task_result.get_status(),
        )
    else:
        logger.debug(
            "Current task id:'%s' and its status: %s.",
            updated_task_result.get_id(),
            updated_task_result.get_status(),
        )

    return MhdAsyncTaskResponse(
        task_id=updated_task_result.get_id(),
        task_status=TaskStatus(updated_task_result.get_status().upper()),
        messages=["Task is submitted for the input file."],
        created_at=datetime.datetime.now(datetime.UTC),
        updated_at=None,
    )


@router.post(
    "/validations/mhd-common-dataset",
    summary="Validate MetabolomicsHub Common Dataset File",
    description="Validate MetabolomicsHub Common Dataset File and return validation results.",
    tags=["Dataset Validation"],
    response_model=MhdAsyncTaskResponse,
)
@inject
async def make_new_dataset_model_validation(
    response: Response,
    file: Annotated[
        UploadFile,
        File(
            title="MetabolomicsHub Common Dataset File",
            description="MetabolomicsHub Common Dataset File.",
        ),
    ],
    cache_service: CacheService = Depends(Provide["services.cache_service"]),  # noqa: FAST002
    async_task_service: AsyncTaskService = Depends(  # noqa: FAST002
        Provide["services.async_task_service"]
    ),
    repository: Annotated[None | RepositoryModel, Depends(validate_api_token)] = None,
):
    if not repository:
        response.status_code = http_status.HTTP_403_FORBIDDEN
        error = "API token is not valid"
        return MhdAsyncTaskResponse(
            errors=[error],
        )

    contents = await file.read()

    file_sha256 = hashlib.sha256(contents).hexdigest()

    file_cache_key = f"new-file-validation-task:{repository.id}:{file_sha256}"
    await cache_service.delete_key(file_cache_key)

    task_id = await cache_service.get_value(file_cache_key)
    if task_id is not None:
        error = "There is a task running for the current file."
        logger.error(error)
        response.status_code = http_status.HTTP_425_TOO_EARLY
        return MhdAsyncTaskResponse(
            task_id=task_id,
            errors=[error],
        )
    task_id = str(uuid.uuid4())

    task_key = f"new-file-validation-task:{repository.id}:{task_id}"
    message = None
    await cache_service.set_value(
        file_cache_key,
        task_id,
        expiration_time_in_seconds=10 * 60,
    )

    await cache_service.set_value(
        task_key,
        file_sha256,
        expiration_time_in_seconds=10 * 60,
    )
    file_json = None
    try:
        file_json = json.loads(contents.decode())
    except Exception:
        message = f"Input file is not valid JSON: {file.filename}"
        logger.error(message)
        return MhdAsyncTaskResponse(
            task_id=task_id,
            task_status=TaskStatus.FAILED,
            messages=[message],
            created_at=None,
            updated_at=None,
        )

    executor = await async_task_service.get_async_task(
        common_dataset_file_validation_task,
        repository_id=repository.id,
        file_json=file_json,
        filename=file.filename,
        task_id=task_id,
        id_generator=IdGenerator(lambda: task_id),
    )

    result = await executor.start()
    task_id = result.get_id()
    logger.info("New file validation task started for the task %s", task_id)
    updated_task_result = None
    try:
        updated_task_result = await async_task_service.get_async_task_result(task_id)
    except Exception:
        message = f"Current file validation task failed to start: {task_id}"
        logger.error(message)
        # await cache_service.delete_key(key)
        # raise AsyncTaskStartFailure(resource_id, task_id, message) from ex
        return MhdAsyncTaskResponse(
            task_id=task_id,
            task_status=TaskStatus.FAILED,
            messages=["Task failed."],
            created_at=datetime.datetime.now(datetime.UTC),
            updated_at=None,
        )

    if updated_task_result.get_status().upper().startswith("FAIL"):
        logger.error(
            "Current task id:'%s' and its status: %s.",
            updated_task_result.get_id(),
            updated_task_result.get_status(),
        )
    else:
        logger.debug(
            "Current task id:'%s' and its status: %s.",
            updated_task_result.get_id(),
            updated_task_result.get_status(),
        )

    return MhdAsyncTaskResponse(
        task_id=updated_task_result.get_id(),
        task_status=TaskStatus(updated_task_result.get_status().upper()),
        messages=["Task is submitted for the input file."],
        created_at=datetime.datetime.now(datetime.UTC),
        updated_at=None,
    )


@router.get(
    "/validations/tasks/{task_id}",
    summary="Check and Get Result of Validation Task",
    description="Check and get result of validation task. Validation results will be stored for up to 60 minutes.",
    tags=["Dataset Validation"],
    response_model=MhdAsyncTaskResponse,
)
@inject
async def get_validation_task(
    response: Response,
    task_id: Annotated[
        str,
        Path(
            title="Task id. ",
            description="task id.",
        ),
    ],
    cache_service: CacheService = Depends(Provide["services.cache_service"]),  # noqa: FAST002
    async_task_service: AsyncTaskService = Depends(  # noqa: FAST002
        Provide["services.async_task_service"]
    ),
    repository: Annotated[None | RepositoryModel, Depends(validate_api_token)] = None,
):
    if not repository:
        response.status_code = http_status.HTTP_400_BAD_REQUEST
        return MhdAsyncTaskResponse(errors=["Invalid API token"])
    task_key = f"new-file-validation-task:{repository.id}:{task_id}"
    task_result_key = f"new-file-validation-task-result:{repository.id}:{task_id}"
    cache_result = await cache_service.get_value(task_result_key)
    if cache_result:
        return MhdAsyncTaskResponse.model_validate_json(cache_result)
    task_result = None
    try:
        task_result = await async_task_service.get_async_task_result(task_id)
        if not task_result.is_ready():
            file_hash = await cache_service.get_value(task_key)
            if file_hash:
                return MhdAsyncTaskResponse(
                    task_id=task_result.get_id(),
                    task_status=TaskStatus(task_result.get_status()),
                    messages=["Task is not completed yet."],
                )
            response.status_code = http_status.HTTP_404_NOT_FOUND
            return MhdAsyncTaskResponse(errors=[f"There is no task {task_id}."])
        try:
            # if task_result.is_successful():
            result = task_result.get()
            output = TaskResult[FileValidationModel].model_validate(result)
            if output.success:
                cache_result = MhdAsyncTaskResponse(
                    task_id=task_result.get_id(),
                    task_status=TaskStatus(task_result.get_status()),
                    result=output.result,
                    errors=output.errors,
                )
                return cache_result

            cache_result = MhdAsyncTaskResponse(
                task_id=task_result.get_id(),
                task_status=TaskStatus.FAILED,
                messages=[output.message] if output.message else None,
                errors=output.errors,
            )
            await cache_service.set_value(
                task_result_key,
                cache_result.model_dump_json(),
                expiration_time_in_seconds=60 * 10,
            )
            task_result.revoke(terminate=True)
            return cache_result
        except Exception as ex:
            response.status_code = http_status.HTTP_400_BAD_REQUEST
            await cache_service.delete_key(task_key)
            return MhdAsyncTaskResponse(
                task_id=task_result.get_id(),
                task_status=TaskStatus.FAILED,
                errors=[str(ex)],
            )
        finally:
            if task_result:
                task_result.revoke()

    except Exception as ex:
        message = f"Current validation task failed to start: {task_id}"
        logger.error(message)
        return MhdAsyncTaskResponse(task_status=TaskStatus.FAILED, errors=[str(ex)])
