from logging import getLogger

from sqlalchemy import select
from sqlalchemy.ext.asyncio.session import AsyncSession

from mhd_ws.infrastructure.persistence.db.db_client import DatabaseClient
from mhd_ws.infrastructure.persistence.db.mhd import (
    ACCESSION_TYPE_PREFIX_MAP,
    AccessionType,
    Dataset,
    DatasetStatus,
    Identifier,
    Repository,
)
from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.dependencies import (
    RepositoryModel,
)

logger = getLogger(__name__)


async def create_new_identifier(
    db_client: DatabaseClient,
    accession_type: AccessionType,
    repository: RepositoryModel,
    dataset_repository_identifier: str,
) -> tuple[Dataset | None, str]:
    async with db_client.session() as a_session:
        session: AsyncSession = a_session
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
            await session.rollback()
            return (
                None,
                f"{repository.name} dataset with identifier {ref_id} already exists.",
            )

        try:
            dataset = Dataset(
                repository=db_repository,
                accession_type=accession_type,
                dataset_repository_identifier=dataset_repository_identifier,
                revision=0,
                status=DatasetStatus.PRIVATE,
            )
            if accession_type == AccessionType.LEGACY:
                dataset.accession = dataset_repository_identifier
            else:
                stmt = (
                    select(Identifier)
                    .where(Identifier.prefix == accession_type.value)
                    .limit(1)
                    .with_for_update()
                )
                result = await session.execute(stmt)
                last_accession = result.scalar_one_or_none()
                if not last_accession:
                    await session.rollback()
                    return None, "Failed to create new MHD identifier."
                last_accession.last_identifier += 1
                prefix = ACCESSION_TYPE_PREFIX_MAP.get(accession_type)
                dataset.accession = f"{prefix}{last_accession.last_identifier:06}"
            session.add(dataset)
            await session.commit()
            await session.refresh(dataset)
            logger.info(
                "New MHD identifier %s created for %s.",
                dataset.accession,
                repository.name,
            )
            return dataset, "New MHD identifier created."

        except Exception as e:
            await session.rollback()
            logger.error("Failed to create new MHD identifier: %s", str(e))
            return None, "Failed to create new MHD identifier."
