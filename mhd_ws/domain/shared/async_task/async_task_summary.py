from typing import Annotated, Generic, TypeVar, Union

from metabolights_utils.common import CamelCaseModel
from pydantic import Field

T = TypeVar("T")


class AsyncTaskStatus(CamelCaseModel):
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


class AsyncTaskSummary(CamelCaseModel, Generic[T]):
    task: Annotated[
        AsyncTaskStatus,
        Field(description="This field contains task information."),
    ] = ""
    task_result: Annotated[
        Union[None, str, T],
        Field(
            description="This field contains result of the task (failure message or success result).",
        ),
    ] = None
