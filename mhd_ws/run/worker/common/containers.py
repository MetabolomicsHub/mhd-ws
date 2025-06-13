from logging import config as logging_config

from dependency_injector import containers, providers

from mhd_ws.application.services.interfaces.async_task.async_task_service import (
    AsyncTaskService,
)
from mhd_ws.application.services.interfaces.async_task.utils import (
    get_async_task_registry,
)
from mhd_ws.application.services.interfaces.cache_service import CacheService

from mhd_ws.domain.domain_services.configuration_generator import (
    create_config_from_dict,
)
from mhd_ws.infrastructure.cache.redis.redis_impl import RedisCacheImpl
from mhd_ws.infrastructure.pub_sub.celery.celery_impl import (
    CeleryAsyncTaskService,
)

from mhd_ws.run.config import ModuleConfiguration
from mhd_ws.run.rest_api.mhd.base_container import (
    GatewaysContainer,
    RepositoriesContainer,
)


class Ws3WorkerCoreContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    logging = providers.Resource(
        logging_config.dictConfig,
        config=config.run.common_worker.logging,
    )

    async_task_registry = providers.Resource(get_async_task_registry)


class Ws3WorkerServicesContainer(containers.DeclarativeContainer):
    config = providers.Configuration()
    core = providers.DependenciesContainer()
    repositories = providers.DependenciesContainer()
    gateways = providers.DependenciesContainer()
    cache_config = providers.Configuration()

    async_task_service: AsyncTaskService = providers.Singleton(
        CeleryAsyncTaskService,
        broker=gateways.pub_sub_broker,
        backend=gateways.pub_sub_backend,
        app_name="default",
        queue_names=["common", "validation", "datamover", "compute", ""],
        async_task_registry=core.async_task_registry,
    )
    cache_service: CacheService = providers.Singleton(
        RedisCacheImpl,
        config=cache_config,
    )


class Ws3WorkerApplicationContainer(containers.DeclarativeContainer):
    config = providers.Configuration(yaml_files=["config.yaml"])
    secrets = providers.Configuration(yaml_files=["config-secrets.yaml"])

    core = providers.Container(
        Ws3WorkerCoreContainer,
        config=config,
    )

    gateways = providers.Container(
        GatewaysContainer,
        config=config.gateways,
    )

    repositories = providers.Container(
        RepositoriesContainer,
        config=config,
        gateways=gateways,
    )

    services = providers.Container(
        Ws3WorkerServicesContainer,
        config=config.services,
        core=core,
        repositories=repositories,
        gateways=gateways,
        cache_config=config.gateways.cache.redis.connection,
    )

    module_config: ModuleConfiguration = providers.Resource(
        create_config_from_dict,
        ModuleConfiguration,
        config.run.common_worker.module_config,
    )
