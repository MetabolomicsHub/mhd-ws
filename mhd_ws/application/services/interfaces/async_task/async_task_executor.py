import abc
from typing import Union

from mhd_ws.application.services.interfaces.async_task.async_task_result import (
    AsyncTaskResult,
)


class AsyncTaskExecutor(abc.ABC):
    @abc.abstractmethod
    async def start(self, expires: Union[None, int] = None) -> AsyncTaskResult: ...
