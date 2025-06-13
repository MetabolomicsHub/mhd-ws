from enum import Enum
from typing import Any, Dict, Generic, List, Union

from fastapi import status
from pydantic import Field
from typing_extensions import Annotated

from mhd_ws.presentation.rest_api.core.base import APIBaseModel, L, T


class Status(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


class DeleteTaskResponse(APIBaseModel):
    deleted: Annotated[
        bool,
        Field(description="Delete task result."),
    ] = True
    task_id: str = ""
    message: str = ""


class APIValidationError(APIBaseModel):
    type: Annotated[
        str,
        Field(description="Validation error type"),
    ] = ""

    loc: Annotated[
        Union[str, List[Union[int, str]]],
        Field(description="Location of the error"),
    ] = ""
    msg: Annotated[
        str,
        Field(description="Error message"),
    ] = ""

    input: Annotated[
        Union[str, Dict[str, Any]],
        Field(description="Input data that caused the error"),
    ] = ""


class APIBaseResponse(APIBaseModel):
    status: Annotated[
        Status,
        Field(description="Status of the response. It can be `success` or `error`"),
    ] = Status.SUCCESS

    success_message: Annotated[
        Union[None, str],
        Field(
            description="If status is `success`, response may contain success message."
            "It may contain a message for partial success even if response status is `error`."
        ),
    ] = None

    error_message: Annotated[
        Union[None, str],
        Field(description="If status is `error`, response may contain error message."),
    ] = None

    errors: Annotated[
        Union[List[str], List[APIValidationError]],
        Field(
            description="If status is `error`, response may contain a list of error details."
        ),
    ] = []


class PaginationParams(APIBaseModel):
    query: Annotated[
        Union[None, str],
        Field(
            description="Query int the request.",
        ),
    ] = None

    skip: Annotated[
        Union[None, int],
        Field(
            description="Skip term in the request.",
        ),
    ] = None
    limit: Annotated[
        Union[None, int],
        Field(
            description="Limit term in the request.",
        ),
    ] = None

    extra_params: Annotated[
        Union[None, Dict[str, Any]],
        Field(
            description="Extra paramaters in the request.",
        ),
    ] = None


example_params = PaginationParams(
    query="control design",
    skip=10,
    limit=10,
    extra_params={"filters": {"factors": {"values": ["age"]}}},
)


class PaginatedResult(APIBaseModel, Generic[T]):
    page: Annotated[List[T], Field(description="Result list of the response.")] = []
    page_size: Annotated[
        int, Field(ge=0, description="Current page's size.", examples=[1])
    ] = 0
    total: Annotated[
        int, Field(ge=0, description="Total items count.", examples=[1234])
    ] = 0
    params: Annotated[
        PaginationParams,
        Field(description="Parameters of the request.", examples=[example_params]),
    ] = PaginationParams()


class APIResponse(APIBaseResponse, Generic[T]):
    """
    API response model for non-paginated results.
    """

    content: Annotated[
        Union[None, T],
        Field(description="If status is `success`, this stores response data."),
    ] = None


class SuccessMessage(APIBaseModel):
    message: str = ""


class APISuccessResponse(APIResponse):
    """
    API default response model for with message.
    """

    content: Annotated[
        SuccessMessage,
        Field(description="If status is `success`, this stores message."),
    ] = SuccessMessage()


class APIListResponse(APIBaseResponse, Generic[L]):
    """
    API response model for non-paginated results. List item can be primitive or any object.
    """

    content: Annotated[
        Union[None, List[L]],
        Field(description="If status is `status`, this stores list of items."),
    ] = None


class APIPaginatedResponse(APIBaseResponse, Generic[T]):
    """
    API response model for paginated results.
    """

    content: Annotated[
        Union[None, PaginatedResult],
        Field(description="Paginated data and metadata of the response."),
    ] = None


class APIErrorResponse(APIBaseResponse):
    """
    API response model for error response.
    `APIErrorResponse` model can be converted to `APIPaginatedResponse`, `APIListResponse` and `APIResponse`.
    """

    status: Annotated[
        Status,
        Field(description="Status of the response. Its value will be `error`"),
    ] = Status.ERROR
    content: Annotated[
        None,
        Field(description="Content will be none"),
    ] = None


PUBLIC_ENDPOINT_ERROR_RESPONSES: Dict[int, APIErrorResponse] = {
    status.HTTP_400_BAD_REQUEST: {"model": APIErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": APIErrorResponse},
    status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": APIErrorResponse},
    status.HTTP_429_TOO_MANY_REQUESTS: {"model": APIErrorResponse},
    status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": APIErrorResponse},
    status.HTTP_501_NOT_IMPLEMENTED: {"model": APIErrorResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": APIErrorResponse},
}

ALL_ERROR_RESPONSES: Dict[int, APIErrorResponse] = {
    status.HTTP_400_BAD_REQUEST: {"model": APIErrorResponse},
    status.HTTP_401_UNAUTHORIZED: {"model": APIErrorResponse},
    status.HTTP_403_FORBIDDEN: {"model": APIErrorResponse},
    status.HTTP_404_NOT_FOUND: {"model": APIErrorResponse},
    status.HTTP_405_METHOD_NOT_ALLOWED: {"model": APIErrorResponse},
    status.HTTP_422_UNPROCESSABLE_ENTITY: {"model": APIErrorResponse},
    status.HTTP_429_TOO_MANY_REQUESTS: {"model": APIErrorResponse},
    status.HTTP_500_INTERNAL_SERVER_ERROR: {"model": APIErrorResponse},
    status.HTTP_501_NOT_IMPLEMENTED: {"model": APIErrorResponse},
    status.HTTP_503_SERVICE_UNAVAILABLE: {"model": APIErrorResponse},
}
