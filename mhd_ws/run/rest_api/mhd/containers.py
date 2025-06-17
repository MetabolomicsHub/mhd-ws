import os
from logging import config as logging_config

from dependency_injector import containers, providers

from mhd_ws.application.context.request_tracker import RequestTracker
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
from mhd_ws.presentation.rest_api.core.models import ApiServerConfiguration
from mhd_ws.run.config import ModuleConfiguration
from mhd_ws.run.rest_api.mhd.base_container import (
    GatewaysContainer,
)


class MhdCoreContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    logging_config = providers.Resource(
        logging_config.dictConfig,
        config=config.run.mhd_ws.logging,
    )
    async_task_registry = providers.Resource(get_async_task_registry)


class MhdServicesContainer(containers.DeclarativeContainer):
    config = providers.Configuration()
    core = providers.DependenciesContainer()

    # repositories = providers.DependenciesContainer()
    gateways = providers.DependenciesContainer()
    cache_config = providers.Configuration()

    # policy_service: PolicyService = providers.Singleton(
    #     OpaPolicyService,
    #     config.policy_service.opa,
    # )

    async_task_service: AsyncTaskService = providers.Singleton(
        CeleryAsyncTaskService,
        broker=gateways.pub_sub_broker,
        backend=gateways.pub_sub_backend,
        app_name="mhd",
        queue_names=["submission"],
        async_task_registry=core.async_task_registry,
    )
    # async_task_service: AsyncTaskService = providers.Singleton(
    #     ThreadingAsyncTaskService,
    #     app_name="mhd",
    #     queue_names=["common", "validation", "datamover", "compute", ""],
    #     async_task_registry=core.async_task_registry,
    # )

    cache_service: CacheService = providers.Singleton(
        RedisCacheImpl,
        config=cache_config,
    )
    # authentication_service: AuthenticationService = providers.Singleton(
    #     MtblsWs2AuthenticationProxy,
    #     config=config.authentication.mtbls_ws2,
    #     cache_service=cache_service,
    #     user_read_repository=repositories.user_read_repository,
    # )
    request_tracker: RequestTracker = providers.Singleton(RequestTracker)
    # authorization_service: AuthorizationService = providers.Singleton(
    #     AuthorizationServiceImpl,
    #     user_read_repository=repositories.user_read_repository,
    #     study_read_repository=repositories.study_read_repository,
    # )

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

    # study_metadata_service_factory: StudyMetadataServiceFactory = providers.Singleton(
    #     MongoDbStudyMetadataServiceFactory,
    #     study_file_repository=repositories.study_file_repository,
    #     investigation_object_repository=repositories.investigation_object_repository,
    #     isa_table_object_repository=repositories.isa_table_object_repository,
    #     isa_table_row_object_repository=repositories.isa_table_row_object_repository,
    #     study_read_repository=repositories.study_read_repository,
    #     temp_path="/tmp/study-metadata-service",
    # )

    # study_metadata_service_factory: StudyMetadataServiceFactory = providers.Singleton(
    #     FileObjectStudyMetadataServiceFactory,
    #     study_file_repository=None,
    #     metadata_files_object_repository=repositories.metadata_files_object_repository,
    #     audit_files_object_repository=repositories.audit_files_object_repository,
    #     study_read_repository=repositories.study_read_repository,
    #     temp_path="/tmp/study-metadata-service",
    # )

    # validation_override_service: ValidationOverrideService = providers.Singleton(
    #     MongoDbValidationOverrideService,
    #     validation_override_repository=repositories.validation_override_repository,
    #     policy_service=policy_service,
    #     validation_overrides_object_key="validation-overrides/validation-overrides.json",
    # )
    # validation_report_service: ValidationReportService = providers.Singleton(
    #     MongoDbValidationReportService,
    #     validation_report_repository=repositories.validation_report_repository,
    #     validation_history_object_key="validation-history",
    # )


MHD_CONFIG_FILE = os.getenv("MHD_CONFIG_FILE", "config.yaml")
MHD_CONFIG_SECRETS_FILE = os.getenv("MHD_CONFIG_SECRETS_FILE", "config-secrets.yaml")

print(f"Using MHD config file: {MHD_CONFIG_FILE}")
print(f"Using MHD secrets file: {MHD_CONFIG_SECRETS_FILE}")


class MhdApplicationContainer(containers.DeclarativeContainer):
    config = providers.Configuration(yaml_files=[MHD_CONFIG_FILE])
    secrets = providers.Configuration(yaml_files=[MHD_CONFIG_SECRETS_FILE])
    core = providers.Container(
        MhdCoreContainer,
        config=config,
    )

    gateways = providers.Container(
        GatewaysContainer,
        config=config.gateways,
    )

    services = providers.Container(
        MhdServicesContainer,
        config=config.services,
        cache_config=config.gateways.cache.redis.connection,
        core=core,
        # repositories=repositories,
        gateways=gateways,
    )

    module_config: ModuleConfiguration = providers.Resource(
        create_config_from_dict,
        config_class=ModuleConfiguration,
        config_dict=config.run.mhd_ws.module_config,
    )

    api_server_config: ApiServerConfiguration = providers.Resource(
        create_config_from_dict,
        config_class=ApiServerConfiguration,
        config_dict=config.run.mhd_ws.api_server_config,
    )
