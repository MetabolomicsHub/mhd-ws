import logging

from starlette.authentication import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
)

from mhd_ws.domain.entities.auth_user import (
    AuthenticatedUser,
    UnauthenticatedUser,
)
from mhd_ws.infrastructure.persistence.db.mhd import Repository

logger = logging.getLogger(__name__)


class AuthBackend(AuthenticationBackend):
    def __init__(self):
        pass

    async def authenticate(self, conn):
        if "Authorization" not in conn.headers:
            return AuthCredentials({"unauthenticated"}), UnauthenticatedUser()

        auth = conn.headers["Authorization"]

        username = await self.validate_credential(auth)

        if not username:
            return AuthCredentials({"unauthenticated"}), UnauthenticatedUser()
        repository: Repository = None
        if not repository:
            logger.error(
                "User role check failure. "
                "User %s details are not fetched by from database.",
                username,
            )
            raise AuthenticationError("User details are not fetched from database")
        scopes = {"authenticated"}
        user = None
        # if user.role == UserRole.SUBMITTER:
        #     scopes.add("submitter")
        # elif user.role == UserRole.CURATOR:
        #     scopes.add("curator")
        #     scopes.add("submitter")
        # elif user.role == UserRole.SYSTEM_ADMIN:
        #     scopes.add("admin")

        return AuthCredentials(scopes), AuthenticatedUser(user)

    async def validate_credential(self, auth: str) -> str:
        username = ""
        password = ""
        jwt = ""
        scheme = ""
        # try:
        #     scheme, credentials = auth.split()
        #     if scheme.lower() == "basic":
        #         decoded = base64.b64decode(credentials).decode("ascii")
        #         username, _, password = decoded.partition(":")
        #     elif scheme.lower() == "bearer":
        #         jwt = credentials
        #     else:
        #         return ""
        # except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
        #     raise AuthenticationError("Invalid auth credentials") from exc
        # if scheme.lower() == "basic" and username:
        #     username = await self.authentication_service.authenticate_with_password(
        #         username, password
        #     )
        # elif scheme.lower() == "bearer" and jwt:
        #     username = await self.authentication_service.validate_token(
        #         TokenType.JWT_TOKEN, jwt
        #     )

        return username
