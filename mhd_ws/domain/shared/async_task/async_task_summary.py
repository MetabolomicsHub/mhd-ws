from typing import Annotated, Generic, TypeVar, Union

from pydantic import Field

from mhd_ws.domain.shared.model import MhdBaseModel

T = TypeVar("T")


class AsyncTaskStatus(MhdBaseModel):
    task_id: Annotated[
        str,
        Field(
            description="This field contains task id of the task.",
        ),
    ] = ""
    task_status: Annotated[
        str,
        Field(
            description="This field contains status of the task. Values: INITIATED, STARTED, SUCCESS, FAILURE, REVOKED, PENDING, etc.",
        ),
    ] = ""
    ready: Annotated[
        bool,
        Field(
            description="This field contains whether the task completed or not.",
        ),
    ] = False
    is_successful: Annotated[
        Union[None, bool],
        Field(
            description="This field contains whether the task completed successfully or not.",
        ),
    ] = None
    message: Annotated[
        str,
        Field(
            description="Message related to the task status.",
        ),
    ] = ""


class AsyncTaskSummary(MhdBaseModel, Generic[T]):
    task: Annotated[
        AsyncTaskStatus,
        Field(description="This field contains task information."),
    ] = AsyncTaskStatus()
    task_result: Annotated[
        Union[None, str, T],
        Field(
            description="This field contains result of the task (failure message or success result).",
        ),
    ] = None
