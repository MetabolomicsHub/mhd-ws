from mhd_ws.application.context.async_task_registry import (
    ASYNC_TASK_REGISTRY,
)


def get_async_task_registry() -> dict:
    return ASYNC_TASK_REGISTRY
