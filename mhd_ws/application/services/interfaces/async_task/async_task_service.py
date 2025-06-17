import uuid
from typing import Callable, Union

from mhd_ws.application.context.async_task_registry import AsyncTaskRegistry
from mhd_ws.application.services.interfaces.async_task.async_task_executor import (
    AsyncTaskExecutor,
)
from mhd_ws.application.services.interfaces.async_task.async_task_result import (
    AsyncTaskResult,
)
from mhd_ws.application.services.interfaces.async_task.conection import (
    PubSubConnection,
)
from mhd_ws.domain.shared.async_task.async_task_description import (
    AsyncTaskDescription,
)


class IdGenerator:
    def __init__(self, generator: Callable = None):
        self.generator = generator

    def generate_unique_id(self) -> str:
        if self.generator:
            return self.generator()
        return str(uuid.uuid4())


class AsyncTaskService:
    def __init__(  # noqa: PLR0913
        self,
        broker: Union[None, PubSubConnection] = None,
        backend: Union[None, PubSubConnection] = None,
        app_name: Union[None, str] = None,
        queue_names: Union[None, list[str]] = None,
        default_queue: Union[None, str] = None,
        async_task_registry: None | AsyncTaskRegistry = None,
    ):
        self.default_queue = default_queue if default_queue else "common"
        self.async_task_registry = (
            async_task_registry if async_task_registry is not None else {}
        )
        self.broker = broker
        self.backend = backend
        self.app_name = app_name if app_name else "default"
        self.queue_names = queue_names if queue_names else [self.default_queue]

    async def get_async_task(
        self,
        task_description: AsyncTaskDescription,
        id_generator: None | IdGenerator = None,
        on_success_task: None | AsyncTaskDescription = None,
        on_failure_task: None | AsyncTaskDescription = None,
        **kwargs,
    ) -> AsyncTaskExecutor: ...

    async def get_async_task_result(
        self,
        task_id: str,
    ) -> AsyncTaskResult: ...
