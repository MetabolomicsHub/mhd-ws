import logging
import time
import traceback
from typing import Any, Union

from asgi_correlation_id import context
from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from mhd_ws.application.context.request_tracker import RequestTracker
from mhd_ws.domain.entities.auth_user import (
    AuthenticatedUser,
    UnauthenticatedUser,
)
from mhd_ws.domain.exceptions.auth import AuthenticationError, AuthorizationError
from mhd_ws.presentation.rest_api.core.responses import APIErrorResponse

logger = logging.getLogger(__name__)


class AuthorizedEndpoint(BaseModel):
    prefix: str


class AuthorizationMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        request_tracker: RequestTracker,
        api_token_authorizations: Union[None, list[dict[str, Any]]] = None,
        signed_jwt_authorizations: Union[None, list[dict[str, Any]]] = None,
    ) -> None:
        super().__init__(app)
        self.request_tracker = request_tracker

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

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        route_path = "/" + str(request.url).removeprefix(str(request.base_url))
        route_path, _, _ = route_path.partition("?")
        user: Union[AuthenticatedUser, UnauthenticatedUser] = request.user
        client_host = request.client.host if request.client else ""
        method = request.method

        try:
            # if api_token_authorization_required:
            #     self.check_initial_authorization(route_path, user, client_host, auth)
            self.set_request_track(
                user, client_host, route_path, user.requested_resource
            )
            if isinstance(user, AuthenticatedUser):
                access_request_message = f"User {user.display_name} requests {method} {route_path} from host/IP {client_host}."
                if user.requested_resource:
                    access_request_message += (
                        f" Target resource id: {user.requested_resource}"
                    )
                if user.requested_resource and not user.resource_owner:
                    logger.warning(access_request_message)
                    raise AuthorizationError(access_request_message)
                # if resource_id:
                # permission_context: StudyPermissionContext = (
                #     await self.authorization_service.get_user_resource_permission(
                #         user.user_detail, resource_id=resource_id
                #     )
                # )
                # self.check_permission_context(
                #     permission_context, client_host, route_path
                # )
                # user.permission_context = permission_context
            else:
                access_request_message = f"Unauthenticated user requests {method} {route_path} from host/IP {client_host}."
                if user.requested_resource:
                    access_request_message += (
                        f" Target resource id: {user.requested_resource}"
                    )
                if user.requested_resource:
                    raise AuthorizationError(access_request_message)
                # if resource_id:
                #     permission_context: StudyPermissionContext = (
                #         await self.authorization_service.get_user_resource_permission(
                #             None, resource_id=resource_id
                #         )
                #     )
                #     self.check_permission_context(
                #         permission_context, client_host, route_path
                #     )
                #     user.permission_context = permission_context

            logger.debug(access_request_message)
            response = await call_next(request)
        except AuthorizationError as ex:
            traceback.print_exc()
            if user.is_authenticated:
                message = f"Authorization error for user {user.display_name}: {str(ex)}"
            else:
                message = f"Authorization error: {str(ex)}"
            logger.debug(message)
            return JSONResponse(
                content=APIErrorResponse(error_message=message).model_dump(),
                status_code=status.HTTP_401_UNAUTHORIZED,
            )
        except AuthenticationError as ex:
            if user.is_authenticated:
                message = (
                    f"Authentication error for user {user.display_name}: {str(ex)}"
                )
                logger.debug(message)
            else:
                message = f"Authentication error for unauthenticated user: {str(ex)}"
                logger.error(message)
            return JSONResponse(
                content=APIErrorResponse(error_message=f"{str(ex)}").model_dump(),
                status_code=status.HTTP_403_FORBIDDEN,
                headers={"WWW-Authenticate": "Bearer"},
            )
        self.set_request_track(
            request.user, client_host, route_path, user.requested_resource
        )
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    # def check_permission_context(
    #     self, context: StudyPermissionContext, client_host: str, route_path: str
    # ):
    #     permission = context.permissions
    #     if (
    #         not permission.read
    #         and not permission.create
    #         and not permission.delete
    #         and permission.update
    #     ):
    #         error_log_message = (
    #             "User %s from host %s has no permission to access %s",
    #             context.user.id_,
    #             client_host,
    #             route_path,
    #         )
    #         logger.error(error_log_message)
    #         raise AuthorizationError(error_log_message)

    def set_request_track(
        self,
        user: Union[UnauthenticatedUser, AuthenticatedUser],
        client_host: str,
        route_path: str,
        resource_id: str,
    ):
        self.request_tracker.route_path_var.set(route_path)
        self.request_tracker.client_var.set(client_host)

        if user.is_authenticated:
            self.request_tracker.user_id_var.set(user.display_name)
        else:
            self.request_tracker.user_id_var.set("-")

        self.request_tracker.resource_id_var.set(resource_id if resource_id else "-")
        self.request_tracker.task_id_var.set("-")
        corr_id = context.correlation_id.get()
        self.request_tracker.request_id_var.set(corr_id or "-")
