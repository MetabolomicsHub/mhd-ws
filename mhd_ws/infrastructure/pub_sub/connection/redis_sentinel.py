from typing import Any, Union

from mhd_ws.application.services.interfaces.async_task.conection import (
    PubSubConnection,
)
from mhd_ws.infrastructure.cache.redis_sentinel.redis_sentinel_config import (
    RedisSentinelConnection,
)


class RedisSentinelConnectionProvider(PubSubConnection):
    def __init__(self, config: Union[RedisSentinelConnection, dict[str, Any]]):
        if isinstance(config, dict):
            self.connection = RedisSentinelConnection.model_validate(config)
            self.redis_configuration = config
        elif isinstance(config, RedisSentinelConnection):
            self.connection = config
            self.redis_configuration = config.model_dump()
        else:
            raise ValueError("Invalid Redis sentinel configuration")

        self.transport_options = {
            "socket_timeout": 2,
            "socket_connect_timeout": 1,
            "master_name": self.connection.master_name,
            "sentinel_kwargs": {"password": self.connection.password},
        }

    def get_configuration(self) -> dict[str, Any]:
        return self.redis_sentinel_configuration

    def get_url(self) -> str:
        sc = self.connection
        return ";".join(
            [
                f"sentinel://:{sc.password}@{service.host}:{service.port}/{sc.db}"
                for service in sc.sentinel_services
            ]
        )

    def get_connection_repr(self) -> str:
        sc = self.connection
        return ";".join(
            [
                f"sentinel://:***@{service.host}:{service.port}/{sc.db}"
                for service in sc.sentinel_services
            ]
        )

    def get_transport_options(self) -> dict[str, Any]:
        return self.transport_options
