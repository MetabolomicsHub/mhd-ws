from dependency_injector import containers, providers

from mhd_ws.application.services.interfaces.async_task.conection import (
    PubSubConnection,
)
from mhd_ws.domain.domain_services.query_planner import QueryPlanner
from mhd_ws.domain.domain_services.search_spec_resolver import SearchSpecResolver
from mhd_ws.domain.entities.search.registries.field_registry import FIELD_REGISTRY
from mhd_ws.domain.entities.search.registries.index_capability_registry import (
    build_index_capabilities,
)
from mhd_ws.infrastructure.persistence.db.db_client import DatabaseClient

# from mhd_ws.infrastructure.persistence.db.mongodb.config import (
#     MongoDbConnection,
# )
from mhd_ws.infrastructure.persistence.db.postgresql.db_client_impl import (
    DatabaseClientImpl,
)
from mhd_ws.infrastructure.pub_sub.connection.redis import RedisConnectionProvider
from mhd_ws.infrastructure.pub_sub.connection.redis_sentinel import (
    RedisSentinelConnectionProvider,
)
from mhd_ws.infrastructure.search.es.advanced_search_gateway import (
    AdvancedSearchGateway,
)
from mhd_ws.infrastructure.search.es.es_configuration import (
    AdvancedSearchConfiguration,
    LegacyElasticSearchConfiguration,
)
from mhd_ws.infrastructure.search.es.legacy.es_legacy_search_gateway import (
    ElasticsearchLegacyGateway,
)
from mhd_ws.infrastructure.search.es_client import ElasticsearchClient


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

    pub_sub_broker: PubSubConnection = providers.Selector(
        config.cache.selected_cache_provider,
        redis=providers.Singleton(
            RedisConnectionProvider,
            config=config.cache.redis.connection,
        ),
        redis_sentinel=providers.Singleton(
            RedisSentinelConnectionProvider,
            config=config.cache.redis_sentinel.connection,
        ),
    )

    pub_sub_backend: PubSubConnection = pub_sub_broker

    elasticsearch_client: ElasticsearchClient = providers.Singleton(
        ElasticsearchClient,
        config=config.database.elasticsearch.connection,
    )

    elasticsearch_legacy_gateway: ElasticsearchLegacyGateway = providers.Singleton(
        ElasticsearchLegacyGateway,
        client=elasticsearch_client,
        config=providers.Factory(
            LegacyElasticSearchConfiguration,
            index_name=config.database.elasticsearch.connection.indices.dataset_legacy,
        ),
    )

    field_registry = providers.Object(FIELD_REGISTRY)
    index_capabilities_registry = providers.Singleton(
        build_index_capabilities,
        dataset_index=config.database.elasticsearch.connection.indices.dataset_legacy,
        metabolite_index=config.database.elasticsearch.connection.indices.metabolite,
        dataset_api_key="dataset_legacy",
        metabolite_api_key="metabolite",
        dataset_ms_index=config.database.elasticsearch.connection.indices.dataset_ms,
        dataset_ms_api_key="dataset_ms",
    )

    search_spec_resolver = providers.Singleton(
        SearchSpecResolver,
        field_registry=field_registry,
    )

    query_planner = providers.Singleton(QueryPlanner)

    advanced_search_gateway = providers.Singleton(
        AdvancedSearchGateway,
        client=elasticsearch_client,
        config=providers.Factory(AdvancedSearchConfiguration),
        planner=query_planner,
        index_registry=index_capabilities_registry,
        field_registry=field_registry,
    )

    mhd_file_base_url = providers.Callable(
        lambda cfg: cfg,
        config.announcement.mhd_file_base_url,
    )


class RepositoriesContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    gateways = providers.DependenciesContainer()
    services = providers.DependenciesContainer()
