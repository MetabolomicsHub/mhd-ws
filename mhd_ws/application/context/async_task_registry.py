from typing import Annotated, Callable

from pydantic import Field

ASYNC_TASK_APP_NAME = Annotated[
    str,
    Field(
        description="async application name",
        default="default",
    ),
]

ASYNC_TASK_QUEUE = Annotated[
    str,
    Field(
        description="queue name to register async task",
        default="common",
    ),
]
ASYNC_TASK_METHOD = Annotated[
    Callable,
    Field(description="method to run as async task"),
]

AsyncTaskRegistry = dict[ASYNC_TASK_APP_NAME, dict[ASYNC_TASK_QUEUE, ASYNC_TASK_METHOD]]


ASYNC_TASK_REGISTRY: AsyncTaskRegistry = {}
