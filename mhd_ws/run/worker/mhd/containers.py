import os
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


class MhdWorkerCoreContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    logging = providers.Resource(
        logging_config.dictConfig,
        config=config.run.common_worker.logging,
    )

    async_task_registry = providers.Resource(get_async_task_registry)


class MhdWorkerServicesContainer(containers.DeclarativeContainer):
    config = providers.Configuration()
    core = providers.DependenciesContainer()
    repositories = providers.DependenciesContainer()
    gateways = providers.DependenciesContainer()
    cache_config = providers.Configuration()

    async_task_service: AsyncTaskService = providers.Singleton(
        CeleryAsyncTaskService,
        broker=gateways.pub_sub_broker,
        backend=gateways.pub_sub_backend,
        app_name="mhd",
        queue_names=["submission"],
        async_task_registry=core.async_task_registry,
    )

    # study_metadata_service_factory: StudyMetadataServiceFactory = providers.Singleton(
    #     FileObjectStudyMetadataServiceFactory,
    #     study_file_repository=None,
    #     metadata_files_object_repository=repositories.metadata_files_object_repository,
    #     audit_files_object_repository=repositories.audit_files_object_repository,
    #     study_read_repository=repositories.study_read_repository,
    #     temp_path="/tmp/study-metadata-service",
    # )
    cache_service: CacheService = providers.Factory(
        RedisCacheImpl,
        config=cache_config,
    )
    # validation_override_service: ValidationOverrideService = providers.Singleton(
    #     FileSystemValidationOverrideService,
    #     file_object_repository=repositories.internal_files_object_repository,
    #     policy_service=policy_service,
    #     validation_overrides_object_key="validation-overrides/validation-overrides.json",
    #     temp_directory="/tmp/validation-overrides-tmp",
    # )
    # validation_report_service: ValidationReportService = providers.Singleton(
    #     FileSystemValidationReportService,
    #     file_object_repository=repositories.internal_files_object_repository,
    #     validation_history_object_key="validation-history",
    # )


MHD_CONFIG_FILE = os.getenv("MHD_CONFIG_FILE", "config.yaml")
MHD_CONFIG_SECRETS_FILE = os.getenv("MHD_CONFIG_SECRETS_FILE", "config-secrets.yaml")


class MhdWorkerApplicationContainer(containers.DeclarativeContainer):
    config = providers.Configuration(yaml_files=[MHD_CONFIG_FILE])
    secrets = providers.Configuration(yaml_files=[MHD_CONFIG_SECRETS_FILE])

    core = providers.Container(
        MhdWorkerCoreContainer,
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
        MhdWorkerServicesContainer,
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
