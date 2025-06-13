import logging
import uuid
from contextlib import asynccontextmanager
from typing import Union

import uvicorn
from asgi_correlation_id import CorrelationIdMiddleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import mhd_ws
from mhd_ws.presentation.rest_api.core import core_router
from mhd_ws.presentation.rest_api.core.exception import exception_handler
from mhd_ws.presentation.rest_api.core.models import ApiServerConfiguration
from mhd_ws.presentation.rest_api.shared.router_utils import add_routers
from mhd_ws.run.config_renderer import render_config_secrets
from mhd_ws.run.module_utils import load_modules
from mhd_ws.run.rest_api.mhd import initialization
from mhd_ws.run.rest_api.mhd.containers import MhdApplicationContainer
from mhd_ws.run.subscribe import find_async_task_modules, find_injectable_modules

logger = None


@asynccontextmanager
async def lifespan(fast_api: FastAPI):
    logger.info(
        "Application initialization. %s",
        "Debug mode is enabled." if fast_api.debug else "Debug mode is disabled.",
    )
    await initialization.init_application()
    logger.info("Application is initialized.")
    yield


def update_container(
    app_name: str = "mhd",
    queue_names: Union[None, list[str]] = None,
    initial_container: Union[None, MhdApplicationContainer] = None,
) -> MhdApplicationContainer:
    if not queue_names:
        queue_names = ["common"]
    global logger  # noqa: PLW0603

    if not initial_container:
        raise TypeError()

    module_config = initial_container.module_config()
    modules = find_async_task_modules(app_name=app_name, queue_names=queue_names)
    async_task_modules = load_modules(modules, module_config)
    modules = find_injectable_modules()
    injectable_modules = load_modules(modules, module_config)
    container = initial_container
    async_module_names = {x.__name__ for x in async_task_modules}
    injectable_module_names = {x.__name__ for x in injectable_modules}
    wirable_module_name = list(async_module_names.union(injectable_module_names))
    render_config_secrets(container.config(), container.secrets())
    container.init_resources()
    # render secrets in config file
    logger = logging.getLogger(__name__)
    container.wire(packages=[mhd_ws.__name__])
    container.wire(
        modules=[
            __name__,
            initialization.__name__,
            *wirable_module_name,
        ]
    )

    logger.info(
        "Registered modules contain async tasks. %s",
        [x.__name__ for x in async_task_modules],
    )
    logger.info(
        "Registered modules contain dependency injections. %s",
        [x.__name__ for x in injectable_modules],
    )
    return container


def create_app(
    app_name="default",
    queue_names: Union[None, list[str]] = None,
    db_connection_pool_size=3,
    container=None,
):
    if not queue_names:
        queue_names = ["common"]
    container = update_container(
        app_name=app_name, queue_names=queue_names, initial_container=container
    )
    container.gateways.runtime_config.db_pool_size.override(db_connection_pool_size)
    server_config: ApiServerConfiguration = container.api_server_config()
    version: str = mhd_ws.__version__

    server_info = server_config.server_info.model_dump()
    swagger_ui_oauth2_redirect_url = "/api/oauth2-redirect"
    app = FastAPI(
        lifespan=lifespan,
        openapi_url="/openapi.json",
        docs_url=None,
        redoc_url=None,
        version=version,
        **server_info,
        debug=True,
        swagger_ui_oauth2_redirect_url=swagger_ui_oauth2_redirect_url,
    )
    app.mount("/resources", StaticFiles(directory="resources"), name="resources")
    app.add_exception_handler(Exception, exception_handler)
    app.include_router(core_router.router)
    for group in server_config.api_groups:
        if group.enabled:
            for router_path in group.router_paths:
                logger.debug("Search routers within %s", router_path)
                add_routers(application=app, root_path=router_path)

    if server_config.cors.origins:
        origin_regex = "|".join(server_config.cors.origins)
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=f"({origin_regex})",
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )

    # app.add_middleware(
    #     AuthorizationMiddleware,
    #     authorization_service=container.services.authorization_service(),
    #     request_tracker=get_request_tracker(),
    #     authorized_endpoints=container.config.run.submission.authorized_endpoints(),
    # )
    # auth_backend = AuthBackend(
    #     authentication_service=container.services.authentication_service(),
    #     user_read_repository=container.repositories.user_read_repository(),
    # )
    # app.add_middleware(AuthenticationMiddleware, backend=auth_backend)
    app.add_middleware(
        CorrelationIdMiddleware,
        header_name="X-Request-ID",
        generator=lambda: str(uuid.uuid4()),
    )
    return app, container


def get_app(
    initial_container: Union[None, MhdApplicationContainer] = None,
    app_name="default",
    queue_names: Union[None, list[str]] = None,
    db_connection_pool_size=3,
):
    if not initial_container:
        initial_container = MhdApplicationContainer()
    fast_app, _ = create_app(
        app_name=app_name,
        queue_names=queue_names,
        db_connection_pool_size=db_connection_pool_size,
        container=initial_container,
    )
    return fast_app


if __name__ == "__main__":
    init_container: MhdApplicationContainer = MhdApplicationContainer()
    fast_app = get_app(initial_container=init_container)
    server_configuration: ApiServerConfiguration = init_container.api_server_config()
    config = server_configuration.server_info
    log_config = init_container.config.run.mhd.logging()
    uvicorn.run(
        fast_app,
        host="0.0.0.0",
        port=server_configuration.port,
        root_path=config.root_path,
        log_config=log_config,
    )
    init_container.shutdown_resources()
