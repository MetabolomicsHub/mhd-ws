from mhd_ws.application.context.async_task_registry import (
    ASYNC_TASK_APP_NAME,
    ASYNC_TASK_QUEUE,
    ASYNC_TASK_REGISTRY,
)
from mhd_ws.domain.shared.async_task.async_task_description import AsyncTaskDescription


def async_task(
    app_name: ASYNC_TASK_APP_NAME = "default", queue: ASYNC_TASK_QUEUE = "common"
):
    def inner(task_method):
        task_name = task_method.__module__ + "." + task_method.__name__
        print(f"Task '{task_name}' for app '{app_name}' and queue '{queue}'")

        def wrapper(**kwargs):
            return task_method(**kwargs)

        executor = AsyncTaskDescription(wrapper, task_name=task_name, queue=queue)
        if app_name not in ASYNC_TASK_REGISTRY:
            ASYNC_TASK_REGISTRY[app_name] = {}
        ASYNC_TASK_REGISTRY[app_name][task_name] = executor
        return executor

    return inner
