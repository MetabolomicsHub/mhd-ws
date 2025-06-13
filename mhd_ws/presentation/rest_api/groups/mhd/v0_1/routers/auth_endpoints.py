import datetime
import hashlib
from logging import getLogger
from typing import Annotated, Union
from uuid import uuid4

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Header, Path, Query, Response, status
from metabolights_utils.common import CamelCaseModel
from pydantic import Field, field_serializer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mhd_ws.application.services.interfaces.cache_service import CacheService
from mhd_ws.infrastructure.persistence.db.mhd import (
    ApiToken,
    ApiTokenStatus,
)
from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.db import get_db
from mhd_ws.presentation.rest_api.groups.mhd.v0_1.routers.dependencies import (
    RepositoryValidation,
    validate_repository_token,
)

logger = getLogger(__name__)

router = APIRouter(tags=["API Tokens"], prefix="/v0_1")


expiration_time_description = """
API token will be invalid after expiration time. 
Its format must comply with ISO 8601 datetime with UTC timezone. 
Example: 2026-03-18T11:40:22Z, 2027-03-18T11:40:22.519222Z
If not defined, the default expiration time will be set to 1 year from the request time. 
"""


class ApiTokenRequestResponse(CamelCaseModel):
    api_token_name: Annotated[
        None | str,
        Field(title="Unique API token name", description="Unique API token name"),
    ] = None
    api_token: Annotated[
        None | str, Field(title="API Token", description="API token")
    ] = None
    expiration_time: Annotated[
        None | datetime.datetime,
        Field(title="Expiration time", description="Expiration time of API token."),
    ] = None
    message: Annotated[
        str, Field(title="Error message", description="Error message")
    ] = None


class ApiTokenModel(CamelCaseModel):
    name: Annotated[
        str,
        Field(title="API token name", description="API token name"),
    ]
    description: Annotated[
        None | str,
        Field(title="API token description", description="API token description"),
    ] = None
    expiration_datetime: Annotated[
        datetime.datetime,
        Field(
            title="API token expiration date time",
            description="API token expiration date time",
        ),
    ]
    status: Annotated[
        ApiTokenStatus,
        Field(title="API token status", description="API token status"),
    ] = ApiTokenStatus.INVALID

    created_at: Annotated[
        datetime.datetime,
        Field(
            title="API token creation date time",
            description="API token creation date time",
        ),
    ]
    modified_at: Annotated[
        None | datetime.datetime,
        Field(
            title="API token modification date time",
            description="API token modification date time",
        ),
    ] = None

    @field_serializer("status")
    @classmethod
    def status_serializer(cls, value):
        if value is None:
            return ""
        if isinstance(value, ApiTokenStatus):
            return value.name
        return value


class ApiTokensResponse(CamelCaseModel):
    repository_name: Annotated[
        None | str, Field(title="Repository name", description="Repository name")
    ] = (None,)
    tokens: Annotated[
        list[ApiTokenModel], Field(title="API tokens", description="API tokens")
    ] = []
    message: Annotated[
        None | str,
        Field(title="API token list message", description="API token list message"),
    ] = (None,)


class ApiTokenValidationResponse(CamelCaseModel):
    valid: Annotated[
        bool,
        Field(
            title="API token validation status",
            description="API token validation status",
        ),
    ] = False
    message: Annotated[
        Union[None, str],
        Field(title="Message", description="Validation related message."),
    ] = None


class ApiTokenInvalidationResponse(CamelCaseModel):
    invalidated: Annotated[
        bool,
        Field(
            title="API token invalidation task status",
            description="API token invalidation task status",
        ),
    ] = False
    message: Annotated[
        Union[None, str],
        Field(title="Message", description="Invalidation task related message."),
    ] = None


@router.post(
    "/api-tokens",
    summary="Create New Repository API Token",
    description="Create new repository API token",
    response_model=ApiTokenRequestResponse,
    responses={
        200: {
            "description": "API token is created.",
        },
        400: {
            "description": "Bad request.",
        },
    },
)
@inject
async def request_new_api_token(
    response: Response,
    name: Annotated[
        str,
        Header(
            title="Unique API token name",
            description="Unique API token name",
            alias="x-name",
        ),
    ],
    description: Annotated[
        None | str,
        Header(
            title="Description of API token",
            description="Description of API token",
            alias="x-description",
        ),
    ] = None,
    expiration_time: Annotated[
        None | datetime.datetime,
        Header(
            title="API token expiration date time.",
            description=expiration_time_description,
            alias="x-expiration-time",
        ),
    ] = None,
    session: Annotated[None | AsyncSession, Depends(get_db)] = None,
    repository_validation: Annotated[
        None | RepositoryValidation, Depends(validate_repository_token)
    ] = None,
    cache_service: CacheService = Depends(
        Provide["services.cache_service"]
    ),  # noqa: FAST002
):
    if not repository_validation.repository:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ApiTokenRequestResponse(message=repository_validation.message)

    api_token = None
    async with session:
        stmt = select(ApiToken).where(ApiToken.name == name)
        result = await session.execute(stmt)
        api_token = result.scalar_one_or_none()

    if api_token:
        message = "API token with this name already exists."
    else:
        exp_time = expiration_time
        if not exp_time:
            exp_time = datetime.datetime.now(
                tz=datetime.timezone.utc
            ) + datetime.timedelta(days=365)
        exp_time = exp_time.replace(tzinfo=None)
        api_token = "mhd_" + str(int(exp_time.timestamp())) + "_" + str(uuid4())
        token_hash = hashlib.sha256(api_token.encode()).hexdigest()
        token = ApiToken(
            repository_id=repository_validation.repository.id,
            name=name,
            token_hash=token_hash,
            expiration_datetime=exp_time,
            status=ApiTokenStatus.VALID,
            description=description,
        )
        try:
            async with session:
                session.add(token)
                await session.commit()
                await session.refresh(token)
            exp_time_str = exp_time.strftime("%Y-%m-%dT%H:%M:%SZ")
            logger.info(
                "API token create with name: %s, expiration time: %s",
                token.name,
                exp_time_str,
            )
            return ApiTokenRequestResponse(
                api_token_name=name,
                api_token=api_token,
                expiration_time=exp_time,
                message="API token is created successfully.",
            )
        except Exception as ex:
            message = "Error creating API token"
            logger.exception(ex)

    logger.error("Error creating API token: %s", message)
    response.status_code = status.HTTP_400_BAD_REQUEST
    return ApiTokenRequestResponse(message=message)


@router.get(
    "/api-tokens",
    summary="Repository API Tokens",
    description="Repository API tokens",
    response_model=ApiTokensResponse,
)
async def get_api_tokens(
    response: Response,
    include_invalid_api_tokens: Annotated[
        None | bool,
        Query(
            title="Include invalid API token", description="Include invalid API token"
        ),
    ] = None,
    name: Annotated[
        str,
        Query(
            title="API token name.",
            description="API token name.",
        ),
    ] = None,
    session: Annotated[None | AsyncSession, Depends(get_db)] = None,
    repository_validation: Annotated[
        None | RepositoryValidation, Depends(validate_repository_token)
    ] = None,
):
    repo = repository_validation.repository
    if not repo:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ApiTokensResponse(message=repository_validation.message)
    if include_invalid_api_tokens:
        query = select(ApiToken)
        if name:
            query = query.where(
                ApiToken.repository_id == repo.id, ApiToken.name == name
            )
        else:
            query = query.where(ApiToken.repository_id == repo.id)
    else:
        if name:
            query = select(ApiToken).where(
                ApiToken.repository_id == repo.id,
                ApiToken.name == name,
                ApiToken.status == ApiTokenStatus.VALID,
            )
        else:
            query = select(ApiToken).where(
                ApiToken.repository_id == repo.id,
                ApiToken.status == ApiTokenStatus.VALID,
            )

    stmt = query.order_by(ApiToken.name.asc())
    async with session:
        result = await session.execute(stmt)
        db_api_tokens = result.scalars().all()
        api_tokens = [
            ApiTokenModel.model_validate(x, from_attributes=True) for x in db_api_tokens
        ]
        return ApiTokensResponse(
            message="Repository API Tokens.",
            tokens=api_tokens,
            repository_name=repo.name,
        )


@router.delete(
    "/api-tokens/{name}",
    summary="Revoke API Token",
    description="Revoke repository API token",
    response_model=ApiTokenInvalidationResponse,
    responses={
        200: {
            "description": "API token is invalidated.",
        },
        401: {
            "description": "Unauthorized request.",
        },
        403: {
            "description": "Forbidden request.",
        },
    },
)
@inject
async def delete_api_token(
    response: Response,
    name: Annotated[
        str,
        Path(
            title="API token name that will be invalidated.",
            description="API token name that will be invalidated.",
        ),
    ],
    session: Annotated[None | AsyncSession, Depends(get_db)] = None,
    repository_validation: Annotated[
        None | RepositoryValidation, Depends(validate_repository_token)
    ] = None,
):
    repo = repository_validation.repository
    if not repo:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ApiTokenInvalidationResponse(
            invalidated=False, message=repository_validation.message
        )
    api_token = None
    try:
        async with session:
            stmt = select(ApiToken).where(ApiToken.name == name)
            result = await session.execute(stmt)
            api_token = result.scalar_one_or_none()
            if not api_token:
                response.status_code = status.HTTP_404_NOT_FOUND
                return ApiTokenInvalidationResponse(
                    invalidated=False, message="API token not found."
                )
            api_token.status = ApiTokenStatus.INVALID
            api_token.modified_at = datetime.datetime.now(
                tz=datetime.timezone.utc
            ).replace(tzinfo=None)
            await session.commit()
        return ApiTokenInvalidationResponse(
            invalidated=True, message="API token is invalidated."
        )
    except Exception as ex:
        response.status_code = status.HTTP_400_BAD_REQUEST
        logger.exception(ex)
        return ApiTokenInvalidationResponse(
            invalidated=False, message="Error deleting API token"
        )


@router.post(
    "/api-tokens/validation",
    summary="Validate API Token",
    description="Validate API token",
    response_model=ApiTokenValidationResponse,
)
@inject
async def check_api_token(
    response: Response,
    api_token: Annotated[
        str,
        Header(
            title="API token that will be validated.",
            description="API token that will be validated.",
            alias="x-api-token",
        ),
    ],
    cache_service: CacheService = Depends(
        Provide["services.cache_service"]
    ),  # noqa: FAST002
    session: Annotated[None | AsyncSession, Depends(get_db)] = None,
    repository_validation: Annotated[
        None | RepositoryValidation, Depends(validate_repository_token)
    ] = None,
):
    repo = repository_validation.repository
    if not repo:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return ApiTokenInvalidationResponse(
            invalidated=False, message=repository_validation.message
        )
    token_hash = hashlib.sha256(api_token.encode()).hexdigest()
    async with session:
        stmt = select(ApiToken).where(
            ApiToken.repository_id == repo.id,
            ApiToken.token_hash == token_hash,
            ApiToken.status == ApiTokenStatus.VALID,
        )
        result = await session.execute(stmt)
        api_token = result.scalar_one_or_none()
        if api_token:
            return ApiTokenValidationResponse(valid=True, message="API token is valid.")
    response.status_code = status.HTTP_400_BAD_REQUEST
    return ApiTokenValidationResponse(valid=False, message="API token is invalid.")
