import logging
import os

from dependency_injector import containers, providers

from mhd_ws.domain.domain_services.configuration_generator import (
    create_config_from_dict,
)
from mhd_ws.infrastructure.cache.redis.redis_config import RedisConnection

logger = logging.getLogger(__name__)

MHD_CONFIG_FILE = os.getenv("MHD_CONFIG_FILE", "mhd-ws-config.yaml")
MHD_CONFIG_SECRETS_FILE = os.getenv(
    "MHD_CONFIG_SECRETS_FILE", ".secrets/.mhd-ws-secrets.yaml"
)

logger.info("Using MHD config file: %s", MHD_CONFIG_FILE)
logger.info("Using MHD secrets file: %s", MHD_CONFIG_SECRETS_FILE)


class Ws3MonitorApplicationContainer(containers.DeclarativeContainer):
    config = providers.Configuration(yaml_files=[MHD_CONFIG_FILE])
    secrets = providers.Configuration(yaml_files=[MHD_CONFIG_SECRETS_FILE])

    celery_broker: RedisConnection = providers.Resource(
        create_config_from_dict,
        RedisConnection,
        config.gateways.cache.redis.connection,
    )
