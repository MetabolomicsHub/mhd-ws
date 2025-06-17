import hashlib
import json
import pathlib
from functools import lru_cache
from logging import getLogger
from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Header
from fastapi.openapi.models import Example
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from mhd_ws.infrastructure.persistence.db.db_client import DatabaseClient
from mhd_ws.infrastructure.persistence.db.mhd import (
    ApiToken,
    ApiTokenStatus,
)
from mhd_ws.presentation.rest_api.core.auth_utils import (
    RepositoryModel,
    RepositoryValidation,
    validate_repository_signed_jwt_token,
)

logger = getLogger(__name__)


@lru_cache(100)
def load_json(file: str):
    with pathlib.Path(file).open("r") as f:
        json_file = json.load(f)
    return json_file


@inject
async def validate_api_token(
    api_token: Annotated[
        str,
        Header(
            title="API token.",
            description="Repository API token",
            alias="x-api-token",
        ),
    ],
    db_client: None | DatabaseClient = Depends(Provide["gateways.database_client"]),
) -> RepositoryModel | None:
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


signed_jwt_token_description = """
Repository public key will be stored on MetabolomicsHub database and signed 
JWT token will be used to validate repository.
The repository application should create a JWT token and sign its payload using the repository private key.

JWT token structure:
- Header
    + Fields
    
        * alg: (Algorithm) payload signing algorithm. It must be "RS256" (RSA Signature with SHA-256)
        * typ: (Type) type of token. It must be "JWT"
    + Example:
    
        {
            "alg": "RS256",
            "typ": "JWT"
        }
- Payload
    * Payload should contain the following fields:
    
        + sub: (Subject) repository name defined in MetabolomicsHub database. 
                It is case sensitive string (e.g., MetaboLights, Metabolomics Workbench, GNPS, etc.)
        + aud: (Audience) MetabolomicsHub portal URL (Valid value: https://www.metabolomicshub.org)
        + iat: (Issued At) Issued time in seconds since the Epoch (IEEE Std 1003.1, 2013 Edition)
        + exp: (Expiration Time) Seconds Since the Epoch (IEEE Std 1003.1, 2013 Edition)
Example:
{
    "sub": <repository name>,
    "aud": "www.metabolomicshub.org",
    "iat": 1678886500,
    "exp": 1678972900
}
- Signature
    * Signature signed by the repository private key using RS256
"""


signed_jwt_token_header = Header(
    title="JWT token signed by the repository",
    description=signed_jwt_token_description,
    openapi_examples={
        "New Token": Example(
            summary="New Signed JWT Token",
            value="",
        ),
        "Test Signed JWT Token": Example(
            summary="Test Signed JWT Token",
            value="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJNZXRhYm9MaWdodHMiLCJhdWQiOiJodHRwczovL3d3dy5tZXRhYm9sb21pY3NodWIub3JnIiwiaWF0IjoxNjk5ODg2NTAwLCJleHAiOjE4OTk5NzI5MDB9.h9hNPcrh8aekGplPdLtvgkEzwPjUBb1TA8TVV-2pBdTofySS2dDsiW_e0HVVy2MqmEeuRiTpT6Wrc2U3XAnEmchy-58Md-UeIdVSNd1F6NW7z2ysHIG_j_g5_sJ4AIHH6U4fHmc8P7mXT8QO9jLU2XLkZ5RCoSioxkpPMjRjmvNr3ugBlDjr13jm-yEcvzdCFq4s4soypnmaYKBZv6ycvcOfb_q6a7qI_w3BQ2ii5kGND5t94VNwxLMF7IqcKlLtVKutD2D1PZKS_bdEu817_oIw8dSqzI00mJBDHjD5rszDkF_9UZAAKb_VxArBewZP955uwpz4t_lackqUs2tXww",
        ),
    },
    alias="x-signed-jwt-token",
)

@inject
async def validate_repository_token(
    signed_jwt_token: Annotated[str, signed_jwt_token_header],
    db_client: DatabaseClient = Depends(Provide["gateways.database_client"]),
) -> None | RepositoryValidation:
    return await validate_repository_signed_jwt_token(signed_jwt_token, db_client)
