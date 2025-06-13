from dependency_injector import containers, providers

from mhd_ws.domain.domain_services.configuration_generator import (
    create_config_from_dict,
)
from mhd_ws.infrastructure.cache.redis.redis_config import RedisConnection


class Ws3MonitorApplicationContainer(containers.DeclarativeContainer):
    config = providers.Configuration(yaml_files=["config.yaml"])

    celery_broker: RedisConnection = providers.Resource(
        create_config_from_dict,
        RedisConnection,
        config.gateways.cache.redis.connection,
    )
