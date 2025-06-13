from typing import Annotated, Union

from mhd_ws.application.context.request_tracker import get_request_tracker
from mhd_ws.presentation.rest_api.shared.data_types import (
    RESOURCE_ID_IN_PATH,
    TASK_ID_IN_PATH,
)


async def get_task_id(task_id: Annotated[Union[None, str], TASK_ID_IN_PATH]):
    get_request_tracker().task_id_var.set(task_id if task_id else "-")

    return task_id


async def get_resource_id(
    resource_id: Annotated[str, RESOURCE_ID_IN_PATH],
):
    get_request_tracker().resource_id_var.set(resource_id if resource_id else "-")

    return resource_id
