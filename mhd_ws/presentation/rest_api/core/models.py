from typing import Annotated

from pydantic import BaseModel, Field

from mhd_ws.presentation.rest_api.core.base import APIBaseModel


class OpenApiTag(BaseModel):
    name: str = ""
    description: str = ""


class ProjectContactConfiguration(BaseModel):
    name: str = ""
    url: str = ""
    email: str = ""


class LicenseInfoConfiguration(BaseModel):
    name: str = ""
    identifier: str = "Apache-2.0"


class CorsConfiguration(BaseModel):
    origins: list[str] = []


class ServerInfo(BaseModel):
    root_path: Annotated[
        str,
        Field(
            description="context path if web service is behind proxy service. e.i. /metabolights/ws3",
        ),
    ] = ""
    title: Annotated[
        str,
        Field(
            description="Title of web service",
        ),
    ] = ""
    summary: str = ""
    description: str = ""
    openapi_tags: list[OpenApiTag] = []
    terms_of_service: str = ""
    contact: ProjectContactConfiguration = ProjectContactConfiguration()
    license_info: LicenseInfoConfiguration = LicenseInfoConfiguration()


class ApiGroup(BaseModel):
    config_name: str = ""
    enabled: bool = False
    router_paths: list[str] = []


class ApiServerConfiguration(APIBaseModel):
    server_info: ServerInfo = ServerInfo()
    api_groups: list[ApiGroup] = []
    cors: CorsConfiguration = CorsConfiguration()
    port: int = 7070


class Version(APIBaseModel):
    version: str = "3.0.0"
    commit_hash: str = ""
    deploy_id: str = ""
