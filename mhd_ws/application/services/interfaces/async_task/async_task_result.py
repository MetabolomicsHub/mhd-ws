import abc
from typing import Any, Union


class AsyncTaskResult(abc.ABC):
    def __init__(self, task_id: str):
        self.id = task_id

    def get_id(self) -> str:
        return self.id

    @abc.abstractmethod
    def get(self, timeout: Union[None, int] = None) -> Any: ...

    @abc.abstractmethod
    def is_ready(self) -> bool: ...

    @abc.abstractmethod
    def is_successful(self) -> bool: ...

    @abc.abstractmethod
    def save(self) -> None: ...

    @abc.abstractmethod
    def revoke(self, terminate: bool = True) -> None: ...

    @abc.abstractmethod
    def get_status(self) -> str: ...
