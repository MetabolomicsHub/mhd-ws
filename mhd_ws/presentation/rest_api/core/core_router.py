from logging import getLogger

from aiocache import cached
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter
from fastapi.openapi import docs
from fastapi.responses import RedirectResponse

from mhd_ws import __version__
from mhd_ws.presentation.rest_api.core.models import ApiServerConfiguration, Version
from mhd_ws.presentation.rest_api.core.responses import APIResponse

logger = getLogger(__name__)

router = APIRouter()


version = Version(version=__version__)
default_response = APIResponse(content=version)


server_config: ApiServerConfiguration = None


@router.get(
    "/version",
    response_model=APIResponse[Version],
    tags=["About API"],
    include_in_schema=False,
)
@cached(ttl=600)
async def get_version_info():
    return default_response


@router.get("/summary", include_in_schema=False)
@inject
async def custom_swagger_ui_html(
    api_server_config: ApiServerConfiguration = Provide["api_server_config"],
):
    config = api_server_config.server_info
    openapi_url = f"{config.root_path}/openapi.json"
    return docs.get_swagger_ui_html(
        openapi_url=openapi_url,
        title=config.title,
        oauth2_redirect_url=f"{config.root_path}/api/oauth2-redirect",
        swagger_js_url=f"{config.root_path}/resources/swagger-ui-bundle.js",
        swagger_css_url=f"{config.root_path}/resources/swagger-ui.css",
        swagger_favicon_url=f"{config.root_path}/resources/favicon.ico",
        swagger_ui_parameters={
            "tryItOutEnabled": True,
            "displayRequestDuration": True,
            "syntaxHighlight": True,
            "syntaxHighlight.activate": True,
            "syntaxHighlight.theme": "agate",
        },
    )


def set_oauth2_redirect_endpoint(api_server_config: ApiServerConfiguration):
    global server_config  # noqa: PLW0603

    def swagger_ui_redirect():
        return docs.get_swagger_ui_oauth2_redirect_html()

    server_config = api_server_config.server_info
    swagger_ui_oauth2_redirect_url = f"{server_config.root_path}/api/oauth2-redirect"

    router.add_api_route(
        swagger_ui_oauth2_redirect_url, swagger_ui_redirect, include_in_schema=False
    )


@router.get("/", include_in_schema=False)
@inject
async def root(
    api_server_config: ApiServerConfiguration = Provide["api_server_config"],
):
    config = api_server_config.server_info
    return RedirectResponse(f"{config.root_path}/summary")


@router.get("/favicon.ico", include_in_schema=False)
@inject
def get_favicon_url(
    api_server_config: ApiServerConfiguration = Provide["api_server_config"],
):
    config = api_server_config.server_info
    return RedirectResponse(f"{config.root_path}/resources/favicon.ico")


@router.get("/docs", include_in_schema=False)
@inject
async def redoc_html(
    api_server_config: ApiServerConfiguration = Provide["api_server_config"],
):
    config = api_server_config.server_info
    openapi_url = f"{config.root_path}/openapi.json"
    return docs.get_redoc_html(
        openapi_url=openapi_url,
        title=config.title + " API Documentation",
        redoc_js_url=f"{config.root_path}/resources/redoc.standalone.js",
        redoc_favicon_url=f"{config.root_path}/resources/favicon.ico",
    )
