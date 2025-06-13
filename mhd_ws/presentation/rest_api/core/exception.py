import logging

from asgi_correlation_id import correlation_id
from fastapi import Request, status
from fastapi.responses import JSONResponse
from jwt import InvalidTokenError

from mhd_ws.domain.exceptions.auth import AuthenticationError, AuthorizationError
from mhd_ws.domain.exceptions.base import NotFoundError, RequestError
from mhd_ws.presentation.rest_api.core.responses import APIErrorResponse

logger = logging.getLogger(__name__)


async def exception_handler(
    request: Request,
    exc: Exception,
) -> APIErrorResponse:
    response_content = APIErrorResponse()
    headers = {"X-Request-ID": correlation_id.get() or ""}
    message = f"{type(exc).__name__}: {str(exc)}"
    error_type = f"{type(exc).__name__}"
    if isinstance(exc, ValueError):
        logger.exception(exc)
        response_content.error_message = error_type
        status_code = status.HTTP_400_BAD_REQUEST
        response_content.errors.append(message)
    elif isinstance(exc, NotFoundError):
        response_content.error_message = error_type
        status_code = status.HTTP_404_NOT_FOUND
        response_content.errors.append(response_content.error_message)
    elif isinstance(exc, (AuthenticationError, InvalidTokenError)):
        logger.warning(message)
        response_content.error_message = error_type
        status_code = status.HTTP_401_UNAUTHORIZED
        response_content.errors.append(message)
        headers = {"WWW-Authenticate": f"error='{message}'"}
    elif isinstance(exc, AuthorizationError):
        # logger.exception(exc)
        response_content.error_message = error_type
        status_code = status.HTTP_401_UNAUTHORIZED
        response_content.errors.append(message)

    else:
        logger.exception(exc)
        if isinstance(exc, RequestError):
            status_code = status.HTTP_400_BAD_REQUEST
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        response_content.error_message = error_type
        response_content.errors.append(message)
    return JSONResponse(
        content=response_content.model_dump(), status_code=status_code, headers=headers
    )
