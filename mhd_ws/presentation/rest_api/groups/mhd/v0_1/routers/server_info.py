import json
from logging import getLogger
from typing import Annotated

from fastapi import APIRouter, Header, Response, status
from fastapi.responses import StreamingResponse
from mhd_model.model.definitions import SUPPORTED_SCHEMA_MAP, SupportedSchemaMap
from mhd_model.schema_utils import load_mhd_json_schema
from pydantic import Field

from mhd_ws.domain.shared.model import MhdBaseModel

logger = getLogger(__name__)

router = APIRouter(tags=["About API"], prefix="/v0_1")


class ProfileResponse(MhdBaseModel):
    # name: Annotated[
    #     str, Field(title="Dataset Model Name", description="Dataset model name")
    # ]
    message: Annotated[str, Field(title="Message", description="Message")]
    # version: Annotated[
    #     str, Field(title="Dataset Model Version", description="Dataset model version")
    # ]


class MhdServerInfo(MhdBaseModel):
    version: Annotated[str, Field(title="Server Version", description="Server version")]
    supported_schemas: Annotated[
        SupportedSchemaMap,
        Field(
            title="Supported schemas and profiles",
            description="Supported schemas and profiles.",
        ),
    ]


server_info = MhdServerInfo(version="0.0.1", supported_schemas=SUPPORTED_SCHEMA_MAP)


@router.get(
    "/server-info",
    summary="MetabolomicsHub Server Information",
    description="Show information about MetabolomicsHub server.",
    response_model=MhdServerInfo,
)
async def get_server_info():
    return server_info


@router.get(
    "/schemas",
    summary="Get announcement file schema and profiles.",
    description="Get announcement file profile.",
)
async def get_profile(
    response: Response,
    uri: Annotated[
        str,
        Header(
            title="Schema or profile URI.",
            description="Schema or profile URI.",
            alias="x-uri",
        ),
    ],
):
    file_name, file_content = load_mhd_json_schema(uri)
    if not file_content:
        response.status_code == status.HTTP_400_BAD_REQUEST
        return ProfileResponse(message="Schema or profile is not found")

    download_filename = f'attachment; filename="{file_name}"'
    headers = {
        "content-type": "application/json",
        "Content-Disposition": download_filename,
    }
    report_chunk_size_in_bytes = 1024 * 1024 * 1

    def iter_content(data: str):
        for i in range(0, len(data), report_chunk_size_in_bytes):
            yield data[i : (i + report_chunk_size_in_bytes)]

    response = StreamingResponse(
        content=iter_content(json.dumps(file_content)), headers=headers
    )
    return response
