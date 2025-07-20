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
from mhd_ws.infrastructure.pub_sub.connection.redis_sentinel import (
    RedisSentinelConnectionProvider,
)


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
        RedisSentinelConnectionProvider,
        config=config.cache.redis_sentinel.connection,
    )

    pub_sub_backend: PubSubConnection = pub_sub_broker


class RepositoriesContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    gateways = providers.DependenciesContainer()
    services = providers.DependenciesContainer()
