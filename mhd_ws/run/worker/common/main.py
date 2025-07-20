import asyncio
import logging
from logging.config import dictConfig
from typing import Any, Sequence, Union

from celery.signals import setup_logging
from dependency_injector.wiring import Provide, inject

import mhd_ws
from mhd_ws.application.services.interfaces.async_task.utils import (
    get_async_task_registry,
)
from mhd_ws.infrastructure.pub_sub.celery.celery_impl import (
    CeleryAsyncTaskService,
)
from mhd_ws.infrastructure.pub_sub.connection.redis_sentinel import (
    RedisSentinelConnectionProvider,
)
from mhd_ws.run.config_renderer import render_config_secrets
from mhd_ws.run.module_utils import load_modules
from mhd_ws.run.rest_api.mhd import initialization
from mhd_ws.run.subscribe import find_async_task_modules, find_injectable_modules
from mhd_ws.run.worker.common.containers import Ws3WorkerApplicationContainer

logger = None


@setup_logging.connect()
@inject
def config_loggers(
    *args,
    config: dict[str, Any] = Provide["config.run.common_worker.logging"],
    **kwargs,
):
    dictConfig(config)


def update_container(
    app_name="default",
    queue_names: Union[None, Sequence[str]] = None,
    initial_container: Union[None, Ws3WorkerApplicationContainer] = None,
) -> Ws3WorkerApplicationContainer:
    global logger  # noqa: PLW0603
    queue_names = queue_names if queue_names else ["common"]

    module_config = initial_container.module_config()
    modules = find_async_task_modules(app_name=app_name, queue_names=queue_names)
    async_task_modules = load_modules(modules, module_config)
    modules = find_injectable_modules()
    injectable_modules = load_modules(modules, module_config)

    if not initial_container:
        raise ValueError("Initial container is not defined")
    render_config_secrets(initial_container.config(), initial_container.secrets())
    initial_container.init_resources()
    initial_container.wire(packages=[mhd_ws.__name__])

    initial_container.wire(modules=[initialization.__name__])
    initial_container.wire(modules=[__name__, *async_task_modules, *injectable_modules])
    logger = logging.getLogger(__name__)

    logger.info(
        "Registered modules contain async tasks. %s",
        [x.__name__ for x in async_task_modules],
    )
    logger.info(
        "Registered modules contain dependency injections. %s",
        [x.__name__ for x in injectable_modules],
    )
    return initial_container


def get_worker_app(initial_container: Ws3WorkerApplicationContainer):
    async_task_registry = get_async_task_registry()

    rc = initial_container.gateways.config.cache.redis_sentinel.connection()
    redis_sentinel_connection_provider = RedisSentinelConnectionProvider(rc)
    manager = CeleryAsyncTaskService(
        broker=redis_sentinel_connection_provider,
        backend=redis_sentinel_connection_provider,
        default_queue="common",
        queue_names=["common"],
        async_task_registry=async_task_registry,
    )

    return manager.app


def get_celery_worker_app():
    initial_container = Ws3WorkerApplicationContainer()
    update_container(
        initial_container=initial_container, app_name="default", queue_names=["common"]
    )
    asyncio.run(
        initialization.init_application(
            test_async_task_service=False, test_policy_service=True
        )
    )
    return get_worker_app(initial_container)


def main():
    app = get_celery_worker_app()
    app.start(
        argv=[
            "worker",
            "-Q",
            "common",
            "--concurrency=1",
            "--loglevel=INFO",
        ]
    )


if __name__ == "__main__":
    main()
