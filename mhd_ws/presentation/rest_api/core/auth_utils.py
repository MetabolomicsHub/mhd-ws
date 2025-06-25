import datetime
import hashlib
from logging import getLogger
from typing import Annotated

import jwt
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from mhd_ws.application.utils.auth_utils import AUDIENCE
from mhd_ws.infrastructure.persistence.db.db_client import DatabaseClient
from mhd_ws.infrastructure.persistence.db.mhd import (
    ApiToken,
    ApiTokenStatus,
    Dataset,
    Repository,
    RepositoryStatus,
)

logger = getLogger(__name__)


class RepositoryModel(BaseModel):
    id: Annotated[int, Field(title="Repository ID", description="Repository ID")]
    name: Annotated[str, Field(title="Repository Name", description="Repository name")]
    description: Annotated[
        None | str,
        Field(title="Repository description", description="Repository description"),
    ] = None
    join_datetime: Annotated[
        datetime.datetime, Field(title="Repository join date", description="join date")
    ]
    status: Annotated[
        RepositoryStatus,
        Field(title="Repository status", description="Repository status"),
    ]
    public_key: Annotated[
        None | str, Field(title="Repository public key", description="Repository key")
    ] = None


class RepositoryValidation(BaseModel):
    repository: Annotated[
        None | RepositoryModel,
        Field(
            title="Repository Name",
            description="Repository name stored on MetabolomicsHub database.",
        ),
    ] = None

    message: Annotated[
        None | str,
        Field(
            title="Validation message",
            description="Validation message. If the repository token is valid, this will be empty.",
        ),
    ] = None


async def validate_api_token(
    api_token: str,
    db_client: DatabaseClient,
) -> None | RepositoryModel:
    token_hash = hashlib.sha256(api_token.encode()).hexdigest()
    async with db_client.session() as session:
        stmt = (
            select(ApiToken)
            .where(
                ApiToken.token_hash == token_hash,
                ApiToken.status == ApiTokenStatus.VALID,
            )
            .options(selectinload(ApiToken.repository))
            .limit(1)
        )
        result = await session.execute(stmt)
        token = result.scalar_one_or_none()
        if not token:
            logger.error("API token not found or not valid.")
            return None
        repository = RepositoryModel.model_validate(
            token.repository, from_attributes=True
        )
        logger.info("%s token validated.", repository.name)
        return repository


async def is_resource_owner(
    resource_id: str,
    repository_id: int,
    db_client: DatabaseClient,
) -> bool:
    async with db_client.session() as session:
        stmt = (
            select(Dataset.accession)
            .where(
                Dataset.repository_id == repository_id, Dataset.accession == resource_id
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        dataset = result.scalar_one_or_none()
        if not dataset:
            logger.error(
                "Repository '%s' does not have a dataset %s.",
                repository_id,
                resource_id,
            )
            return False
        return True


async def validate_repository_signed_jwt_token(
    signed_jwt_token: str,
    db_client: DatabaseClient,
) -> None | RepositoryValidation:
    token = signed_jwt_token
    options = {"require": ["exp", "sub", "iat", "sub"]}
    message = None
    repository_model = None
    try:
        decoded: dict[str, str] = jwt.decode(
            token, "", options={"verify_signature": False}
        )
        sub = decoded.get("sub")

        if sub:
            async with db_client.session() as session:
                stmt = select(Repository).where(
                    Repository.name == sub, Repository.status == RepositoryStatus.ACTIVE
                )
                result = await session.execute(stmt)
                repo = result.scalar_one_or_none()
                if not repo:
                    message = f"Repository '{sub}' is not found or not active."
                    logger.error(message)
                else:
                    public_key = repo.public_key
                    if public_key:
                        decoded = jwt.decode(
                            jwt=token,
                            key=public_key,
                            options=options,
                            audience=AUDIENCE,
                            algorithms=["RS256"],
                        )
                        logger.info("%s signed JWT token is validated.", repo.name)
                        repository_model = RepositoryModel.model_validate(
                            repo, from_attributes=True
                        )
                        return RepositoryValidation(
                            repository=repository_model, message=message
                        )
                    else:
                        message = f"{repo.name} repository public key is not found."
                        logger.error(message)
        else:
            message = "Repository name not defined."
            logger.error(message)
    except Exception as ex:
        message = "Error decoding JWT token : " + str(ex)
        logger.exception(ex)

    return RepositoryValidation(message=message)
