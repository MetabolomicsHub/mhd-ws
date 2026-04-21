"""DI container for the announcement derivation CLI command."""

from __future__ import annotations

from logging import config as logging_config

from dependency_injector import containers, providers

from mhd_ws.infrastructure.persistence.db.postgresql.db_client_impl import (
    DatabaseClientImpl,
)


class AnnouncementCliCoreContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    logging = providers.Resource(
        logging_config.dictConfig,
        config=config.run.cli.logging,
    )


class AnnouncementCliGatewaysContainer(containers.DeclarativeContainer):
    config = providers.Configuration()

    database_client = providers.Singleton(
        DatabaseClientImpl,
        db_connection=config.database.postgresql.connection,
    )


class AnnouncementCliContainer(containers.DeclarativeContainer):
    config = providers.Configuration()
    secrets = providers.Configuration()

    core = providers.Container(
        AnnouncementCliCoreContainer,
        config=config,
    )

    gateways = providers.Container(
        AnnouncementCliGatewaysContainer,
        config=config.gateways,
    )
