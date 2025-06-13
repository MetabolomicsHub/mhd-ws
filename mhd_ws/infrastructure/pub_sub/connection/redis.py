from typing import Any, Union

from mhd_ws.application.services.interfaces.async_task.conection import PubSubConnection
from mhd_ws.infrastructure.cache.redis.redis_config import RedisConnection


class RedisConnectionProvider(PubSubConnection):
    def __init__(self, config: Union[RedisConnection, dict[str, Any]]):
        if isinstance(config, dict):
            self.connection = RedisConnection.model_validate(config)
            self.redis_configuration = config
        elif isinstance(config, RedisConnection):
            self.connection = config
            self.redis_configuration = config.model_dump()
        else:
            raise ValueError("Invalid Redis configuration")

        self.transport_options = {
            "socket_timeout": 2,
            "socket_connect_timeout": 1,
        }

    def get_configuration(self) -> dict[str, Any]:
        return self.redis_configuration

    def get_url(self) -> str:
        rc = self.connection
        return f"redis://:{rc.password}@{rc.redis_service.host}:{rc.redis_service.port}/{rc.db}"

    def get_connection_repr(self) -> str:
        rc = self.connection
        return f"redis://:***@{rc.redis_service.host}:{rc.redis_service.port}/{rc.db}"

    def get_transport_options(self) -> dict[str, Any]:
        return self.transport_options
