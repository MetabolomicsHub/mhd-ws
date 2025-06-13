import logging
import re
import time
from typing import Union

from asgi_correlation_id import context
from fastapi import Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.authentication import AuthCredentials
from starlette.middleware.base import BaseHTTPMiddleware

from mhd_ws.application.context.request_tracker import RequestTracker

from mhd_ws.domain.entities.auth_user import AuthenticatedUser, UnauthenticatedUser
from mhd_ws.domain.exceptions.auth import AuthenticationError, AuthorizationError
from mhd_ws.presentation.rest_api.core.responses import APIErrorResponse

logger = logging.getLogger(__name__)


class AuthorizedEndpoint(BaseModel):
    prefix: str
    scopes: set[str]


class AuthorizationMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        request_tracker: RequestTracker,
        authorized_endpoints: Union[None, list[AuthorizedEndpoint]] = None,
    ) -> None:
        super().__init__(app)
        self.request_tracker = request_tracker

        self.authorized_endpoints = (
            [AuthorizedEndpoint.model_validate(x) for x in authorized_endpoints]
            if authorized_endpoints
            else []
        )

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        route_path = "/" + str(request.url).removeprefix(str(request.base_url))
        route_path, _, _ = route_path.partition("?")
        auth: AuthCredentials = request.auth
        user: Union[AuthenticatedUser, UnauthenticatedUser] = request.user
        client_host = request.client.host
        resource_id = None
        method = request.method
        match = re.match(r".*/(REQ[1-9][0-9]*|MTBLS[1-9][0-9]*)(/.*|$)", route_path)
        if match:
            resource_id = match.groups()[0]
        try:
            self.set_request_track(user, client_host, route_path, resource_id)
            self.check_initial_authorization(route_path, user, client_host, auth)

            if user.is_authenticated:
                access_request_message = f"User {user.user_detail.id_} requests {method} {route_path} from host/IP {client_host}."
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
                access_request_message = f"Unauthenticated user requests {method} {route_path} from host/IP {client_host}."
            if resource_id:
                access_request_message += f" Target resource id: {resource_id}"
            logger.debug(access_request_message)

            response = await call_next(request)
        except AuthorizationError as ex:
            if user.is_authenticated:
                message = (
                    f"Authorization error for user {user.user_detail.id_}: {str(ex)}"
                )
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
                    f"Authentication error for user {user.user_detail.id_}: {str(ex)}"
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
        self.set_request_track(request.user, client_host, route_path, resource_id)
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

    def check_initial_authorization(
        self,
        route_path: str,
        user: Union[AuthenticatedUser, UnauthenticatedUser],
        client_host: str,
        auth: AuthCredentials,
    ):
        scope_match = False
        authorized_path = False
        for authorized_endpoint in self.authorized_endpoints:
            if route_path.startswith(authorized_endpoint.prefix):
                authorized_path = True
                if authorized_endpoint.scopes.intersection(set(auth.scopes)):
                    scope_match = True
                    break

        if authorized_path and not scope_match:
            if user.is_authenticated:
                error_log_message = (
                    "User %s from host %s has no permission to access %s",
                    user.user_detail.id_,
                    client_host,
                    route_path,
                )
                logger.error(error_log_message)
                raise AuthorizationError(error_log_message)
            logger.error(
                "Unauthenticated user requested the authorized %s resource from host %s",
                route_path,
                client_host,
            )
            raise AuthenticationError(
                f"Authentication is required to access {route_path}."
            )

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
            self.request_tracker.user_id_var.set(user.user_detail.id_)
        else:
            self.request_tracker.user_id_var.set(0)

        self.request_tracker.resource_id_var.set(resource_id if resource_id else "-")
        self.request_tracker.task_id_var.set("-")

        self.request_tracker.request_id_var.set(context.correlation_id.get())
