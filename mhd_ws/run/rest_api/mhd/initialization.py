import logging

from dependency_injector.wiring import Provide, inject

from mhd_ws.application.services.interfaces.async_task.async_task_result import (
    AsyncTaskResult,
)
from mhd_ws.application.services.interfaces.async_task.async_task_service import (
    AsyncTaskService,
)
from mhd_ws.application.services.interfaces.cache_service import CacheService
from mhd_ws.infrastructure.persistence.db.db_client import DatabaseClient
from mhd_ws.run.rest_api.mhd.mhd_ping import ping_connection

logger = logging.getLogger(__name__)


@inject
async def init_application(  # noqa: PLR0913
    database_client: DatabaseClient = Provide["gateways.database_client"],
    cache_service: CacheService = Provide["services.cache_service"],
    async_task_service: AsyncTaskService = Provide["services.async_task_service"],
    # user_read_repository: UserReadRepository = Provide[
    #     "repositories.user_read_repository"
    # ],
    # policy_service: PolicyService = Provide["services.policy_service"],
    test_database_connection: bool = True,
    test_cache_service: bool = True,
    test_async_task_service: bool = True,
    # test_database_table: bool = True,
    # test_policy_service: bool = False,
):
    if test_database_connection:
        await init_database_client(database_client)
    if test_cache_service:
        await init_cache_service(cache_service)
    if test_async_task_service:
        await init_async_task_service(async_task_service)
    # if test_database_table:
    #     await init_user_repository(user_read_repository)
    # if test_policy_service:
    #     await init_policy_service(policy_service)


def get_service_name(service) -> str:
    return f"{service.__module__}.{service.__class__.__name__}"


# async def init_policy_service(policy_service: PolicyService) -> bool:
#     if not policy_service:
#         logger.info("OPA service is not initialized.")
#         return False

#     try:
#         result = await policy_service.get_supported_validation_versions()

#         if result:
#             logger.info(
#                 "Open Policy Agent is ready to run validations on: %s",
#                 await policy_service.get_service_url(),
#             )
#         else:
#             raise Exception("Unexpected ping response from OPA config", str(result))
#     except Exception as ex:
#         logger.error("OPA is not ready: %s", str(ex))
#         logger.critical("Validation tasks will fail.")
#         return False
#     return True


async def init_cache_service(cache_service: CacheService) -> bool:
    if not cache_service:
        logger.info("Cache service is not initialized.")
        return False

    cache_url = await cache_service.get_connection_repr()
    logger.info("Cache service connection: %s.", cache_url)
    cache_service_name = (
        f"{cache_service.__module__}.{cache_service.__class__.__name__}"
    )
    try:
        result = await cache_service.ping()
        if result:
            logger.info("Cache service is initialised: %s", cache_service_name)
        else:
            raise Exception(f"Unexpected ping response from cache service: {result}")
    except Exception as ex:
        logger.error(
            "Cache service initialisation failed: %s. %s", cache_service_name, str(ex)
        )
        logger.critical("Any service or method that uses cache service may fail.")
        return False
    return True


async def init_async_task_service(async_task_service: AsyncTaskService) -> bool:
    if not async_task_service:
        logger.info("Async task service is not initialized.")
        return False
    async_task_service_name = (
        f"{async_task_service.__module__}.{async_task_service.__class__.__name__}"
    )

    logger.info(
        "Async task service '%s' is initialized: %s.",
        async_task_service.app_name,
        async_task_service_name,
    )
    logger.info(
        "Async task service managed queues: '%s' (default: %s).",
        ",".join(async_task_service.queue_names),
        async_task_service.default_queue,
    )
    if async_task_service.broker:
        logger.info(
            "Async task service broker connection: %s.",
            async_task_service.broker.get_connection_repr(),
        )
    else:
        logger.warning("Async task service has no broker.")
    if async_task_service.backend:
        logger.info(
            "Async task service backend connection: %s",
            async_task_service.backend.get_connection_repr(),
        )
    else:
        logger.warning("Async task service has no backed.")

    data_input = {"ping": "pong"}
    executor = await async_task_service.get_async_task(ping_connection, data="ping")

    try:
        future_result: AsyncTaskResult = await executor.start(expires=1)
        result = future_result.get(timeout=1)
        if future_result.is_successful() and result == data_input["ping"]:
            logger.info("Async task service connection is successfull.")
        else:
            if isinstance(result, Exception):
                raise result
            raise Exception(str(result))
    except Exception as ex:
        error = str(ex)
        if "timeout" in ex.__class__.__name__.lower():
            logger.critical("%s connection timeout", async_task_service_name)
            logger.critical("Async tasks will fail if a backend worker will not start.")
        else:
            logger.exception(
                "%s connection failed with output (expected: '%s'): %s.",
                async_task_service_name,
                data_input["ping"],
                error,
                exc_info=ex,
            )
            logger.critical("Async tasks will fail if a backend worker will not start.")
        return False
    return True


# async def init_user_repository(user_read_repository: UserReadRepository) -> bool:
#     if not user_read_repository:
#         logger.info("User repository is not initialized.")
#         return False
#     user_read_repository_name = get_service_name(user_read_repository)

#     logger.info("User repository initialized:  %s", user_read_repository_name)
#     try:
#         result = await user_read_repository.find(query_options=QueryOptions(limit=1))

#         if result.data:
#             logger.info("User repository connection is successfull.")
#         else:
#             logger.error("There is no user in database.")
#             logger.error("Any service or method that uses user repository may fail.")
#             return False
#     except Exception as ex:
#         logger.error("User repository connection failed with output: %s.", str(ex))
#         logger.error("Any service or method that uses user repository may fail.")
#         return False

#     return True


async def init_database_client(database_client: DatabaseClient):
    if not database_client:
        logger.info("Database client is not initialized.")
        return
    database_client_name = get_service_name(database_client)
    logger.info("Database client initialized: %s", database_client_name)
    logger.info("Database connection: %s", await database_client.get_connection_repr())
