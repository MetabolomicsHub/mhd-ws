import abc
from typing import Any


class PubSubConnection(abc.ABC):
    @abc.abstractmethod
    def get_configuration(self) -> dict[str, Any]: ...

    @abc.abstractmethod
    def get_url(self) -> str: ...

    @abc.abstractmethod
    def get_connection_repr(self) -> str: ...

    @abc.abstractmethod
    def get_transport_options(self) -> dict[str, Any]: ...
