import asyncio
import datetime
import hashlib
import json
import uuid
from io import StringIO
from logging import getLogger
from typing import Any, OrderedDict

import httpx
import jsonschema
from dependency_injector.wiring import Provide, inject
from jsonschema import exceptions
from mhd_model.model.definitions import SUPPORTED_SCHEMA_MAP
from mhd_model.model.v0_1.announcement.profiles.base.profile import (
    AnnouncementBaseProfile,
)
from mhd_model.model.v0_1.announcement.validation.validator import (
    MhdAnnouncementFileValidator,
)
from mhd_model.model.v0_1.dataset.validation.validator import MhdFileValidator
from mhd_model.shared.model import ProfileEnabledDataset
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mhd_ws.application.decorators.async_task import async_task
from mhd_ws.application.services.interfaces.async_task.async_task_service import AsyncTaskService
from mhd_ws.application.services.interfaces.cache_service import CacheService
from mhd_ws.infrastructure.persistence.db.db_client import DatabaseClient
from mhd_ws.infrastructure.announcement.mhd_model_adapter import (
    convert_mhd_to_announcement,
)
from mhd_ws.infrastructure.persistence.db.mhd import (
    AccessionType,
    AnnouncementFile,
    Dataset,
    DatasetRevision,
    DatasetRevisionStatus,
    DatasetStatus,
)
from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.models import (
    CreateDatasetRevisionModel,
    DatasetRevisionError,
    FileValidationModel,
    TaskResult,
)

logger = getLogger(__name__)


def json_path(field_path):
    return ".".join([x if isinstance(x, str) else f"[{x}]" for x in field_path])


def validate_announcement_file(announcement_file_json: dict[str, Any]):
    validator = MhdAnnouncementFileValidator()

    all_errors = validator.validate(announcement_file_json)
    errors = OrderedDict()
    for idx, x in enumerate(all_errors, start=1):
        errors[str(idx)] = x
    return errors


def validate_common_dataset_file(file_json: dict[str, Any]):
    mhd_validator = MhdFileValidator()
    errors = mhd_validator.validate(file_json)

    def json_path(field_path):
        return ".".join([x if isinstance(x, str) else f"[{x}]" for x in field_path])

    validation_errors = [(json_path(x.absolute_path), x) for x in errors]

    all_errors = [x for x in validation_errors]

    def update_context(
        error: jsonschema.ValidationError, parent: jsonschema.ValidationError
    ):
        error.parent = parent
        if error.context:
            for item in error.context:
                if isinstance(item, jsonschema.ValidationError):
                    item.parent = error
                    update_context(item, error)

    errors: OrderedDict = OrderedDict(
        [
            (
                str(idx),
                f"{json_path(x.absolute_path)}: {exceptions.best_match([x]).message}",
            )
            for idx, x in enumerate(all_errors)
        ]
    )

    return errors


@inject
async def add_submission(
    repository_id: str,
    accession: str,
    announcement_file_json: dict[str, Any],
    announcement_reason: str,
    task_id: str,
    database_client: DatabaseClient = Provide["gateways.database_client"],
    cache_service: CacheService = Provide["services.cache_service"],
):
    file_cache_key = f"new-announcement:{accession}"
    message = None
    try:
        logger.info("Checking announcement file for %s", accession)

        errors = validate_announcement_file(announcement_file_json)
        if errors:
            logger.error("%s announcement file has errors", accession)
            return TaskResult[CreateDatasetRevisionModel](
                success=False, message="Announcement file is not valid.", errors=errors
            ).model_dump()
        logger.info("Announcement file schema is validated for %s", accession)

        logger.info("Checked announcement file schema for %s", accession)
        announcement = AnnouncementBaseProfile.model_validate(announcement_file_json)
        mhd_metadata_file_url = announcement.mhd_metadata_file_url
        mhd_file = StringIO()
        try:
            with httpx.Client() as client:
                r = client.get(mhd_metadata_file_url)
                r.raise_for_status()
                mhd_file = StringIO(r.text)
                mhd_file_json = json.loads(mhd_file.read())
                errors = validate_common_dataset_file(mhd_file_json)
                if errors:
                    logger.error(
                        "%s mhd file on %s has errors", accession, mhd_metadata_file_url
                    )
                    return TaskResult[CreateDatasetRevisionModel](
                        success=False, message="MHD file is not valid.", errors=errors
                    ).model_dump()
                logger.info("MHD file schema is validated for %s", accession)

        except Exception as e:
            logger.error(
                "Failed to get mhd common data model file from URL %s",
                mhd_metadata_file_url,
            )
            return TaskResult[CreateDatasetRevisionModel](
                success=False,
                message="Failed to get mhd metadata file.",
                errors={str(e)},
            ).model_dump()
        repository_revision = announcement.repository_revision
        repository_revision_datetime = announcement.repository_revision_datetime
        if repository_revision_datetime:
            repository_revision_datetime = repository_revision_datetime.astimezone(
                datetime.timezone.utc
            )

        file_str = json.dumps(announcement_file_json)
        file_sha256 = hashlib.sha256(file_str.encode()).hexdigest()

        now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)

        logger.info("Adding dataset revision for %s", accession)
        async with database_client.session() as a_session:
            try:
                session: AsyncSession = a_session
                stmt = (
                    select(Dataset)
                    .where(
                        Dataset.accession == accession,
                        Dataset.repository_id == repository_id,
                    )
                    .limit(1)
                    .with_for_update()
                )
                result = await session.execute(stmt)
                db_dataset = result.scalar_one_or_none()

                if db_dataset is None:
                    raise DatasetRevisionError(
                        f"Dataset {accession} not found in the database."
                    )
                stmt = select(DatasetRevision).where(
                    DatasetRevision.dataset_id == db_dataset.id,
                    DatasetRevision.revision == db_dataset.revision,
                )
                result = await session.execute(stmt)
                latest_revision = result.scalar_one_or_none()
                if latest_revision:
                    stmt = select(AnnouncementFile.hash_sha256).where(
                        AnnouncementFile.id == latest_revision.file_id,
                    )
                    result = await session.execute(stmt)
                    latest_file_sha256 = result.scalar()
                    if latest_file_sha256 and latest_file_sha256 == file_sha256:
                        raise DatasetRevisionError(
                            f"Dataset {accession} has the same file already submitted."
                        )
                profile_enabled_dataset = ProfileEnabledDataset.model_validate(
                    announcement_file_json
                )
                schema_uri = (
                    profile_enabled_dataset.schema_name
                    or SUPPORTED_SCHEMA_MAP.schemas[
                        SUPPORTED_SCHEMA_MAP.default_schema_uri
                    ]
                )
                if profile_enabled_dataset.profile_uri:
                    profile_uri = profile_enabled_dataset.profile_uri
                else:
                    profile_uri = schema_uri.default_profile_uri

                announcement_file = AnnouncementFile(
                    dataset=db_dataset,
                    hash_sha256=file_sha256,
                    file=announcement_file_json,
                    schema_uri=schema_uri,
                    profile_uri=profile_uri,
                )
                stmt = select(func.max(DatasetRevision.revision)).where(
                    DatasetRevision.dataset_id == db_dataset.id
                )
                result = await session.execute(stmt)
                max_revision = result.scalar()
                revision = db_dataset.revision + 1
                if max_revision is not None:
                    if max_revision > db_dataset.revision:
                        revision = max_revision + 1

                dataset_revision = DatasetRevision(
                    dataset=db_dataset,
                    file=announcement_file,
                    task_id=task_id,
                    revision=revision,
                    revision_datetime=now,
                    description=announcement_reason,
                    repository_revision=repository_revision,
                    repository_revision_datetime=repository_revision_datetime,
                    status=DatasetRevisionStatus.VALID,
                )
                db_dataset.updated_at = now
                db_dataset.revision = revision
                db_dataset.revision_datetime = now
                db_dataset.status = DatasetStatus.PUBLIC

                session.add(announcement_file)
                session.add(dataset_revision)
                await session.commit()
                # await session.refresh(announcement_file)
                # await session.refresh(dataset_revision)
                logger.info(
                    "Dataset %s has new revision %s at %s",
                    db_dataset.accession,
                    dataset_revision.revision,
                    dataset_revision.revision_datetime,
                )
                model = CreateDatasetRevisionModel.model_validate(
                    dataset_revision, from_attributes=True
                )
                model.accession = accession
                return TaskResult[CreateDatasetRevisionModel](
                    success=True, result=model
                ).model_dump()
            except DatasetRevisionError as ex:
                message = str(ex)
                await session.rollback()
                logger.error(message)
            except Exception as ex:
                message = f"Failed to add submission task for {accession}"
                logger.error(message)
                logger.exception(ex)
                await session.rollback()

    except jsonschema.ValidationError as ex:
        message = f"Failed to validate file content for {accession}"
        logger.error(message)
        logger.exception(ex)
        # raise ex
    except Exception as ex:
        message = f"Failed to get file content for {accession}"
        logger.error(message)
        logger.exception(ex)
        # raise ex
    finally:
        await cache_service.delete_key(file_cache_key)
    return TaskResult[CreateDatasetRevisionModel](
        success=False, message=message
    ).model_dump()


@async_task(app_name="mhd", queue="submission")
def add_submission_task(
    *,
    repository_id: str,
    accession: str,
    announcement_file_json: dict[str, Any],
    announcement_reason: str,
    task_id: str,
    **kwargs,
) -> str:
    coroutine = add_submission(
        repository_id=repository_id,
        accession=accession,
        announcement_file_json=announcement_file_json,
        announcement_reason=announcement_reason,
        task_id=task_id,
    )
    return asyncio.run(coroutine)


@inject
async def announcement_file_validation(
    repository_id: str,
    announcement_file_json: dict[str, Any],
    filename: str,
    task_id: str,
    cache_service: CacheService = Provide["services.cache_service"],
):
    file_str = json.dumps(announcement_file_json)
    file_sha256 = hashlib.sha256(file_str.encode()).hexdigest()

    file_cache_key = f"new-announcement-validation:{repository_id}:{file_sha256}"
    task_key = f"new-file-validation-task:{repository_id}:{task_id}"
    message = None
    input_file_info = FileValidationModel(
        task_id=task_id,
        file=filename,
        repository_name=announcement_file_json.get("repository_name", ""),
        repository_id=repository_id,
        schema_uri=announcement_file_json.get("$schema", ""),
        profile_uri=announcement_file_json.get("profile_uri", ""),
        mhd_identifier=announcement_file_json.get("mhd_identifier", ""),
        dataset_repository_identifier=announcement_file_json.get(
            "repository_identifier", ""
        ),
        repository_revision=announcement_file_json.get("repository_revision", None),
        repository_revision_datetime=announcement_file_json.get(
            "repository_revision_datetime", None
        ),
    )
    errors = {}
    try:
        logger.info("Checking announcement file for the task %s", task_id)

        errors = validate_announcement_file(announcement_file_json)
        if errors:
            logger.error("Announcement file has error for the task %s", task_id)
            result = TaskResult[FileValidationModel](
                success=False,
                message="Announcement file is not valid.",
                errors=errors,
                result=input_file_info,
            ).model_dump()
            return result
        logger.info("Announcement file schema is validated for the task %s", task_id)

        logger.info("Checked announcement file schema for the task %s", task_id)
        result = TaskResult[FileValidationModel](
            success=True, message="Announcement file is valid.", result=input_file_info
        ).model_dump()

        return result

    except jsonschema.ValidationError as ex:
        message = f"Failed to validate file content for the task {task_id}"
        logger.error(message)
        logger.exception(ex)
        errors["validation"] = message
        # raise ex
    except Exception as ex:
        message = f"Failed to get file content for the task {task_id}"
        logger.error(message)
        logger.exception(ex)
        errors["failure"] = message
        # raise ex
    finally:
        await cache_service.delete_key(file_cache_key)
        await cache_service.delete_key(task_key)

    result = TaskResult[FileValidationModel](
        success=False, message=message, errors=errors, result=input_file_info
    ).model_dump()
    return result


@async_task(app_name="mhd", queue="submission")
def announcement_file_validation_failure(result: dict[str, Any]) -> str:
    return "Announcement file validation task failed."


@async_task(app_name="mhd", queue="submission")
def announcement_file_validation_task(
    *,
    repository_id: str,
    announcement_file_json: dict[str, Any],
    filename: str | None = None,
    task_id: str,
    **kwargs,
) -> str:
    coroutine = announcement_file_validation(
        repository_id=repository_id,
        announcement_file_json=announcement_file_json,
        filename=filename or "",
        task_id=task_id,
    )
    return asyncio.run(coroutine)


@inject
async def common_dataset_file_validation(
    repository_id: int,
    file_json: dict[str, Any],
    filename: str | None,
    task_id: str,
    cache_service: CacheService = Provide["services.cache_service"],
):
    file_str = json.dumps(file_json)
    file_sha256 = hashlib.sha256(file_str.encode()).hexdigest()

    file_cache_key = f"new-file-validation:{repository_id}:{file_sha256}"
    task_key = f"new-file-task:{repository_id}:{task_id}"
    message = None
    input_file_info = FileValidationModel(
        task_id=task_id,
        file=filename or "",
        repository_name=file_json.get("repository_name", ""),
        repository_id=repository_id,
        schema_uri=file_json.get("$schema", ""),
        profile_uri=file_json.get("profile_uri", ""),
        mhd_identifier=file_json.get("mhd_identifier", ""),
        dataset_repository_identifier=file_json.get("repository_identifier", ""),
        repository_revision=file_json.get("repository_revision", None),
        repository_revision_datetime=file_json.get(
            "repository_revision_datetime", None
        ),
    )

    try:
        logger.info("Checking file with the task %s", task_id)

        errors = validate_common_dataset_file(file_json)
        if errors:
            logger.error("File has errors with the task %s", task_id)
            return TaskResult[FileValidationModel](
                success=False,
                message="File is not valid.",
                errors=errors,
                result=input_file_info,
            ).model_dump()
        logger.info("File schema is validated with the task %s", task_id)

        return TaskResult[FileValidationModel](
            success=True,
            message="File is valid.",
            result=input_file_info,
        ).model_dump()

    except jsonschema.ValidationError as ex:
        message = f"Failed to validate file content for the task {task_id}"
        logger.error(message)
        logger.exception(ex)
        # raise ex
    except Exception as ex:
        message = f"Failed to get file content for the task {task_id}"
        logger.error(message)
        logger.exception(ex)
        # raise ex
    finally:
        await cache_service.delete_key(file_cache_key)
        await cache_service.delete_key(task_key)
    return TaskResult[FileValidationModel](
        success=False,
        message=message,
        result=input_file_info,
        errors={"failure": message},
    ).model_dump()


@async_task(app_name="mhd", queue="submission")
def common_dataset_file_validation_task(
    *,
    repository_id: int,
    file_json: dict[str, Any],
    filename: str | None = None,
    task_id: str,
    **kwargs,
) -> str:
    coroutine = common_dataset_file_validation(
        repository_id=repository_id,
        file_json=file_json,
        filename=filename or "",
        task_id=task_id,
    )
    return asyncio.run(coroutine)


@inject
async def derive_announcement(
    accession: str,
    mhd_file_url: str = "",
    mhd_file: dict[str, Any] | None = None,
    announcement_file: dict[str, Any] | None = None,
    reason: str = "Derived from mhd.json",
    task_id: str | None = None,
    database_client: DatabaseClient = Provide["gateways.database_client"],
    cache_service: CacheService | None = Provide["services.cache_service"],
) -> dict[str, Any]:
    task_id = task_id or str(uuid.uuid4())

    if announcement_file is not None:
        # Pre-converted announcement provided — skip fetch and conversion entirely.
        announcement_json = announcement_file
    else:
        # Step 1: Fetch mhd.json (skipped when mhd_file is provided directly)
        if mhd_file is None:
            try:
                with httpx.Client() as client:
                    response = client.get(mhd_file_url)
                    response.raise_for_status()
                    mhd_file = json.loads(response.text)
            except Exception as e:
                return {"success": False, "message": f"Failed to fetch mhd.json: {e}"}
        mhd_file_json = mhd_file

        # Step 2: Detect profile
        async with database_client.session() as a_session:
            session: AsyncSession = a_session
            stmt = select(Dataset).where(Dataset.accession == accession).limit(1)
            result = await session.execute(stmt)
            db_dataset = result.scalar_one_or_none()
            if db_dataset is None:
                return {"success": False, "message": f"Dataset {accession!r} not found in database."}
            profile = (
                "legacy"
                if db_dataset.accession_type in (AccessionType.LEGACY, AccessionType.TEST_LEGACY)
                else "ms"
            )

        # Step 3: Convert mhd.json to announcement
        try:
            announcement_json = convert_mhd_to_announcement(mhd_file_json, mhd_file_url, profile=profile)
        except Exception as e:
            return {"success": False, "message": f"Conversion failed: {e}"}

    # Step 4: Sha256 dedup + store
    announcement_sha256 = hashlib.sha256(json.dumps(announcement_json).encode()).hexdigest()

    async with database_client.session() as a_session:
        try:
            session: AsyncSession = a_session
            stmt = (
                select(Dataset)
                .where(Dataset.accession == accession)
                .limit(1)
                .with_for_update()
            )
            result = await session.execute(stmt)
            db_dataset = result.scalar_one_or_none()

            if db_dataset is None:
                await session.rollback()
                return {"success": False, "message": f"Dataset {accession!r} not found in database."}

            if db_dataset.revision > 0:
                stmt = select(DatasetRevision).where(
                    DatasetRevision.dataset_id == db_dataset.id,
                    DatasetRevision.revision == db_dataset.revision,
                )
                result = await session.execute(stmt)
                latest_revision = result.scalar_one_or_none()
                if latest_revision:
                    stmt = select(AnnouncementFile.hash_sha256).where(
                        AnnouncementFile.id == latest_revision.file_id,
                    )
                    result = await session.execute(stmt)
                    existing_sha256 = result.scalar()
                    if existing_sha256 == announcement_sha256:
                        return {"success": False, "message": f"Announcement for {accession} is unchanged."}

            # Step 5: Determine URIs
            profile_enabled_dataset = ProfileEnabledDataset.model_validate(announcement_json)
            schema_uri = (
                profile_enabled_dataset.schema_name
                or SUPPORTED_SCHEMA_MAP.schemas[SUPPORTED_SCHEMA_MAP.default_schema_uri]
            )
            if profile_enabled_dataset.profile_uri:
                profile_uri = profile_enabled_dataset.profile_uri
            else:
                profile_uri = schema_uri.default_profile_uri

            # Step 6: Store
            stmt = select(func.max(DatasetRevision.revision)).where(
                DatasetRevision.dataset_id == db_dataset.id
            )
            result = await session.execute(stmt)
            max_revision = result.scalar()
            new_revision = db_dataset.revision + 1
            if max_revision is not None:
                if max_revision > db_dataset.revision:
                    new_revision = max_revision + 1

            now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)

            announcement_file = AnnouncementFile(
                dataset=db_dataset,
                hash_sha256=announcement_sha256,
                file=announcement_json,
                schema_uri=schema_uri,
                profile_uri=profile_uri,
            )
            dataset_revision = DatasetRevision(
                dataset=db_dataset,
                file=announcement_file,
                task_id=task_id,
                revision=new_revision,
                revision_datetime=now,
                description=reason,
                status=DatasetRevisionStatus.VALID,
            )
            db_dataset.updated_at = now
            db_dataset.revision = new_revision
            db_dataset.revision_datetime = now
            db_dataset.status = DatasetStatus.PUBLIC

            session.add(announcement_file)
            session.add(dataset_revision)
            await session.commit()

            logger.info(
                "Dataset %s derived new announcement revision %s",
                accession,
                new_revision,
            )
        except Exception as e:
            await session.rollback()
            logger.exception(e)
            return {"success": False, "message": str(e)}

    # Step 7: Invalidate cache
    if cache_service is not None:
        await cache_service.delete_key(f"announcement-file:{accession}:latest")

    # Step 8: Return success
    return {"success": True, "message": f"Announcement derived as revision {new_revision}."}


@async_task(app_name="mhd", queue="submission")
def derive_announcement_task(
    *,
    accession: str,
    mhd_file_url: str,
    mhd_file: dict[str, Any] | None = None,
    reason: str = "Derived from mhd.json",
    task_id: str | None = None,
    **kwargs,
) -> str:
    coroutine = derive_announcement(
        accession=accession,
        mhd_file_url=mhd_file_url,
        mhd_file=mhd_file,
        reason=reason,
        task_id=task_id,
    )
    return asyncio.run(coroutine)


@inject
async def derive_all_announcements(
    mhd_file_base_url: str,
    reason: str = "Batch re-derivation",
    database_client: DatabaseClient = Provide["gateways.database_client"],
    async_task_service: AsyncTaskService = Provide["services.async_task_service"],
) -> dict[str, Any]:
    """Dispatch derive_announcement_task for every dataset in the DB.

    The mhd.json URL for each dataset is constructed as:
        {mhd_file_base_url}/{accession}.mhd.json
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    dispatched = 0
    errors = []

    async with database_client.session() as a_session:
        session: AsyncSession = a_session
        stmt = select(Dataset.accession)
        result = await session.execute(stmt)
        accessions = [row[0] for row in result.all()]

    for accession in accessions:
        mhd_file_url = f"{mhd_file_base_url.rstrip('/')}/{accession}.mhd.json"
        try:
            executor = await async_task_service.get_async_task(
                derive_announcement_task,
                accession=accession,
                mhd_file_url=mhd_file_url,
                reason=reason,
            )
            await executor.start()
            dispatched += 1
        except Exception as e:
            logger.error("Failed to dispatch derivation for %s: %s", accession, e)
            errors.append(f"{accession}: {e}")

    return {
        "success": True,
        "dispatched": dispatched,
        "errors": errors,
    }


@async_task(app_name="mhd", queue="submission")
def derive_all_announcements_task(
    *,
    mhd_file_base_url: str,
    reason: str = "Batch re-derivation",
    **kwargs,
) -> str:
    coroutine = derive_all_announcements(
        mhd_file_base_url=mhd_file_base_url,
        reason=reason,
    )
    return asyncio.run(coroutine)
