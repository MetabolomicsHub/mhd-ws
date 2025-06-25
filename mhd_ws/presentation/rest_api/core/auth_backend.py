import logging
import re
from typing import Any

from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
)

from mhd_ws.domain.entities.auth_user import (
    AuthenticatedUser,
    UnauthenticatedUser,
)
from mhd_ws.infrastructure.persistence.db.db_client import DatabaseClient
from mhd_ws.presentation.rest_api.core.auth_utils import (
    RepositoryValidation,
    is_resource_owner,
    validate_api_token,
    validate_repository_signed_jwt_token,
)
from mhd_ws.presentation.rest_api.core.authorization_middleware import (
    AuthorizedEndpoint,
)

logger = logging.getLogger(__name__)


class AuthBackend(AuthenticationBackend):
    def __init__(
        self,
        db_client: DatabaseClient,
        api_token_authorizations: None | list[dict[str, Any]] = None,
        signed_jwt_authorizations: None | list[dict[str, Any]] = None,
    ) -> None:
        self.db_client = db_client

        self.api_token_authorizations = (
            [AuthorizedEndpoint.model_validate(x) for x in api_token_authorizations]
            if api_token_authorizations
            else []
        )
        self.signed_jwt_authorizations = (
            [AuthorizedEndpoint.model_validate(x) for x in signed_jwt_authorizations]
            if signed_jwt_authorizations
            else []
        )

    async def authenticate(self, conn):
        # if (
        #     "x-signed-jwt-token" not in conn.headers
        #     or "x-api-token" not in conn.headers
        # ):
        #     return AuthCredentials(["unauthenticated"]), UnauthenticatedUser()

        resource_id = self.fetch_resource_id(conn.url.path)
        signed_jwt_authorization_required = False
        for endpoint in self.signed_jwt_authorizations:
            if conn.url.path.startswith(endpoint.prefix):
                signed_jwt_authorization_required = True
                break

        api_token_authorization_required = False
        for endpoint in self.api_token_authorizations:
            if conn.url.path.startswith(endpoint.prefix):
                api_token_authorization_required = True
                break

        if signed_jwt_authorization_required:
            auth = conn.headers.get("x-signed-jwt-token")
            if not auth:
                logger.error("Signed JWT token is missing.")
                raise AuthenticationError("Signed JWT token is missing")

            validation: (
                None | RepositoryValidation
            ) = await validate_repository_signed_jwt_token(auth, self.db_client)

            if not validation or not validation.repository:
                logger.error("Repository check failure.")
                raise AuthenticationError(
                    "Repository details are not fetched from database"
                )
            scopes = ["authenticated"]
            scopes.append("repository")
            resource_owner = (
                await is_resource_owner(
                    resource_id=resource_id,
                    repository_id=validation.repository.id,
                    db_client=self.db_client,
                )
                if resource_id and validation.repository
                else None
            )
            return AuthCredentials(scopes), AuthenticatedUser(
                validation.repository.name, resource_id, resource_owner=resource_owner
            )
        elif api_token_authorization_required:
            api_token = conn.headers.get("x-api-token")
            if not api_token:
                logger.error("API token is missing.")
                raise AuthenticationError("API token is missing.")

            repository = await validate_api_token(
                api_token=api_token,
                db_client=self.db_client,
            )
            if repository:
                scopes = ["authenticated"]
                scopes.append("repository")
                resource_owner = (
                    await is_resource_owner(
                        resource_id=resource_id,
                        repository_id=repository.id,
                        db_client=self.db_client,
                    )
                    if resource_id and repository.id > 0
                    else None
                )
                return AuthCredentials(scopes), AuthenticatedUser(
                    repository.name, resource_id, resource_owner=resource_owner
                )
            raise AuthenticationError("Unauthorized access.")
        else:
            logger.error("No authentication method provided.")
            return AuthCredentials(["unauthenticated"]), UnauthenticatedUser(
                resource_id
            )

    RESOURCE_REGEX = r".*/(MHD[A-Z][0-9]{1,8})(/.*|$)"

    def fetch_resource_id(self, route_path: str) -> str:
        match = re.match(self.RESOURCE_REGEX, route_path)
        resource_id = ""
        if match:
            resource_id = match.groups()[0]
        return resource_id
