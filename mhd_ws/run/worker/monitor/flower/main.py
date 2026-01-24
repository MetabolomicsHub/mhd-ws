import logging
from logging.config import dictConfig
from typing import Any, Union

from celery import Celery
from celery.signals import setup_logging
from dependency_injector.wiring import Provide, inject

from mhd_ws.application.services.interfaces.async_task.utils import (
    get_async_task_registry,
)
from mhd_ws.infrastructure.pub_sub.celery.celery_impl import (
    CeleryAsyncTaskService,
)
from mhd_ws.infrastructure.pub_sub.connection.redis import RedisConnectionProvider
from mhd_ws.run.worker.monitor.flower.containers import (
    Ws3MonitorApplicationContainer,
)

logger: Union[None, logging.Logger] = None


@setup_logging.connect()
@inject
def config_loggers(
    *args,
    config: dict[str, Any] = Provide["config.run.common_worker.logging"],
    **kwargs,
):
    dictConfig(config)


def initiate_container(
    container: Union[None, Ws3MonitorApplicationContainer] = None,
) -> Ws3MonitorApplicationContainer:
    global logger  # noqa: PLW0603

    if not container:
        raise ValueError("Initial container is not defined")

    container.init_resources()

    logger = logging.getLogger(__name__)
    return container


def get_flower_app(container: Ws3MonitorApplicationContainer) -> Celery:
    async_task_registry = get_async_task_registry()

    rc = container.redis_connection()
    redis_connection_provider = RedisConnectionProvider(rc)
    manager = CeleryAsyncTaskService(
        broker=redis_connection_provider,
        backend=redis_connection_provider,
        default_queue="common",
        queue_names=["common"],
        async_task_registry=async_task_registry,
    )

    return manager.app


def main(container: Ws3MonitorApplicationContainer):
    container = initiate_container(container=container)
    app = get_flower_app(container)
    port = container.config.run.monitor.port()
    if not port or not isinstance(port, int):
        if logger:
            logger.warning(
                "Port configuration is not valid. Default port 5555 will be used."
            )
        port = 5555
    app.start(argv=["flower", f"--port={port}"])


if __name__ == "__main__":
    init_container = Ws3MonitorApplicationContainer()
    main(container=init_container)
