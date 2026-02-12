from logging import config as logging_config

from dependency_injector import containers, providers

from mhd_ws.infrastructure.search.es_client import ElasticsearchClient


class IndexingCoreContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    logging = providers.Resource(
        logging_config.dictConfig,
        config=config.run.cli.logging,
    )


class IndexingGatewaysContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    elasticsearch_client: ElasticsearchClient = providers.Singleton(
        ElasticsearchClient,
        config=config.database.elasticsearch.connection,
    )


class IndexingCliContainer(containers.DeclarativeContainer):
    config = providers.Configuration()
    secrets = providers.Configuration()

    core = providers.Container(
        IndexingCoreContainer,
        config=config,
    )

    gateways = providers.Container(
        IndexingGatewaysContainer,
        config=config.gateways,
    )
