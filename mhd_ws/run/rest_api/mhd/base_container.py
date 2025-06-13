from dependency_injector import containers, providers

from mhd_ws.application.services.interfaces.async_task.conection import (
    PubSubConnection,
)
from mhd_ws.infrastructure.persistence.db.db_client import DatabaseClient

# from mhd_ws.infrastructure.persistence.db.mongodb.config import (
#     MongoDbConnection,
# )
from mhd_ws.infrastructure.persistence.db.postgresql.db_client_impl import (
    DatabaseClientImpl,
)
from mhd_ws.infrastructure.pub_sub.connection.redis import RedisConnectionProvider


class GatewaysContainer(containers.DeclarativeContainer):
    config = providers.Configuration()
    runtime_config = providers.Configuration()
    database_client: DatabaseClient = providers.Singleton(
        DatabaseClientImpl,
        db_connection=config.database.postgresql.connection,
        db_pool_size=runtime_config.db_pool_size,
    )

    # mongodb_connection: MongoDbConnection = providers.Resource(
    #     create_config_from_dict,
    #     MongoDbConnection,
    #     config.database.mongodb.connection,
    # )

    pub_sub_broker: PubSubConnection = providers.Singleton(
        RedisConnectionProvider,
        config=config.cache.redis.connection,
    )

    pub_sub_backend: PubSubConnection = pub_sub_broker


class RepositoriesContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    gateways = providers.DependenciesContainer()
    services = providers.DependenciesContainer()
    # study_read_repository: StudyReadRepository = providers.Singleton(
    #     SqlDbStudyReadRepository,
    #     entity_mapper=entity_mapper,
    #     alias_generator=alias_generator,
    #     database_client=gateways.database_client,
    # )

    # user_write_repository: UserWriteRepository = providers.Singleton(
    #     SqlDbUserWriteRepository,
    #     entity_mapper=entity_mapper,
    #     alias_generator=alias_generator,
    #     database_client=gateways.database_client,
    # )

    # user_read_repository: UserReadRepository = providers.Singleton(
    #     SqlDbUserReadRepository,
    #     entity_mapper=entity_mapper,
    #     alias_generator=alias_generator,
    #     database_client=gateways.database_client,
    # )
    # # study_file_repository: StudyFileRepository = providers.Singleton(
    # #     MongoDbStudyFileRepository,
    # #     connection=gateways.mongodb_connection,
    #     study_objects_collection_name="study_files",
    # )

    # study_file_repository: StudyFileRepository = providers.Singleton(
    #     SqlDbStudyFileRepository,
    #     entity_mapper=entity_mapper,
    #     alias_generator=alias_generator,
    #     database_client=gateways.database_client,
    # )

    # folder_manager = providers.Singleton(
    #     StudyFolderManager, config=config.repositories.study_folders
    # )

    # internal_files_object_repository: FileObjectWriteRepository = providers.Singleton(
    #     FileSystemObjectWriteRepository,
    #     folder_manager=folder_manager,
    #     study_bucket=StudyBucket.INTERNAL_FILES,
    #     observer=None,
    # )
    # audit_files_object_repository: FileObjectWriteRepository = providers.Singleton(
    #     FileSystemObjectWriteRepository,
    #     folder_manager=folder_manager,
    #     study_bucket=StudyBucket.AUDIT_FILES,
    #     observer=None,
    # )
    # metadata_files_object_repository: FileObjectWriteRepository = providers.Singleton(
    #     FileSystemObjectWriteRepository,
    #     folder_manager=folder_manager,
    #     study_bucket=StudyBucket.PRIVATE_METADATA_FILES,
    #     observer=None,
    # )
    # investigation_object_repository: InvestigationObjectRepository = (
    #     providers.Singleton(
    #         MongoDbInvestigationObjectRepository,
    #         connection=gateways.mongodb_connection,
    #         collection_name="investigation_files",
    #         study_bucket=StudyBucket.PRIVATE_METADATA_FILES,
    #         observer=study_file_repository,
    #     )
    # )
    # isa_table_object_repository: IsaTableObjectRepository = providers.Singleton(
    #     MongoDbIsaTableObjectRepository,
    #     connection=gateways.mongodb_connection,
    #     collection_name="isa_table_files",
    #     study_bucket=StudyBucket.PRIVATE_METADATA_FILES,
    #     observer=study_file_repository,
    # )
    # isa_table_row_object_repository: IsaTableRowObjectRepository = providers.Singleton(
    #     MongoDbIsaTableRowObjectRepository,
    #     connection=gateways.mongodb_connection,
    #     collection_name="isa_table_rows",
    #     study_bucket=StudyBucket.PRIVATE_METADATA_FILES,
    # )
    # validation_override_repository: ValidationOverrideRepository = providers.Singleton(
    #     MongoDbValidationOverrideRepository,
    #     connection=gateways.mongodb_connection,
    #     collection_name="validation_overrides",
    #     observer=study_file_repository,
    # )
    # validation_report_repository: ValidationReportRepository = providers.Singleton(
    #     MongoDbValidationReportRepository,  # noqa: F821
    #     connection=gateways.mongodb_connection,
    #     study_bucket=StudyBucket.INTERNAL_FILES,
    #     collection_name="validation_reports",
    #     validation_history_object_key="validation-history",
    #     observer=study_file_repository,
    # )
