import logging
from typing import Callable, OrderedDict, Union

from celery import Celery, chain, group
from celery.result import AsyncResult

from mhd_ws.application.context.async_task_registry import AsyncTaskRegistry
from mhd_ws.application.context.request_tracker import get_request_tracker
from mhd_ws.application.services.interfaces.async_task.async_task_executor import (
    AsyncTaskExecutor,
)
from mhd_ws.application.services.interfaces.async_task.async_task_result import (
    AsyncTaskResult,
)
from mhd_ws.application.services.interfaces.async_task.async_task_service import (
    AsyncTaskService,
    IdGenerator,
)
from mhd_ws.application.services.interfaces.async_task.conection import PubSubConnection
from mhd_ws.domain.exceptions.async_task import AsyncTaskError, AsyncTaskNotFoundError
from mhd_ws.domain.shared.async_task.async_task_description import AsyncTaskDescription
from mhd_ws.infrastructure.pub_sub.celery.base_task import CeleryBaseTask

logger = logging.getLogger(__name__)


class CeleryTaskRouter:
    def __init__(
        self,
        app_name: str,
        default_queue: str,
        async_task_dict: dict[str, AsyncTaskDescription],
    ) -> None:
        self.async_task_dict = async_task_dict
        self.app_name = app_name
        self.default_queue = default_queue

    def route_task(self, name, args, kwargs, options, task=None, **kw):
        if name not in self.async_task_dict:
            return {"queue": self.default_queue}
        return {"queue": self.async_task_dict[name].queue}


class CeleryAsyncTaskResult(AsyncTaskResult):
    def __init__(self, task: AsyncResult, is_group: bool = False):
        super().__init__(task.id)
        self.task = task
        self.is_group = is_group

    def get(self, timeout: int = 10):
        return self.task.get(timeout=timeout)

    def is_ready(self) -> bool:
        return self.task.ready()

    def is_successful(self) -> bool:
        return self.task.successful()

    def save(
        self,
        timeout: int = 10,
    ):
        self.task.save()

    def revoke(self, terminate: bool = True):
        if self.task.ready():
            self.task.forget()
        return self.task.revoke(terminate=terminate)

    def get_status(self) -> str:
        return self.task.status


class CeleryAsyncTaskExecutor(AsyncTaskExecutor):
    def __init__(
        self, task_method: Callable, task_name: str, id_generator: IdGenerator, **kwargs
    ):
        self.task_method = task_method
        self.kwargs = kwargs
        self.task_name = task_name
        self.id_generator = id_generator

    async def start(self, expires: Union[None, int] = None) -> AsyncTaskResult:
        request_tracker = get_request_tracker().get_request_tracker_model().model_dump()
        self.kwargs["request_tracker"] = request_tracker
        if self.id_generator:
            task_id = self.id_generator.generate_unique_id()
            task = self.task_method.apply_async(
                expires=expires,
                kwargs=self.kwargs,
                task_id=task_id,
            )
        else:
            task = self.task_method.apply_async(expires=expires, kwargs=self.kwargs)
        logger.info("Task '%s' is created.", self.task_name)
        return CeleryAsyncTaskResult(task)


class CeleryAsyncTaskService(AsyncTaskService):
    def __init__(  # noqa: PLR0913
        self,
        broker: Union[None, PubSubConnection] = None,
        backend: Union[None, PubSubConnection] = None,
        app_name: Union[None, str] = None,
        queue_names: Union[None, list[str]] = None,
        default_queue: Union[None, str] = None,
        async_task_registry: Union[None, AsyncTaskRegistry] = None,
    ):
        super().__init__(
            broker, backend, app_name, queue_names, default_queue, async_task_registry
        )
        self.app_dict: dict[str, Celery] = {}
        self.app_tasks: dict[str, dict[str, dict[str, Callable]]] = {}

        self.app = self._create_async_app(
            broker, backend, app_name, queue_names, default_queue
        )

    def _create_async_app(
        self,
        broker: Union[None, PubSubConnection] = None,
        backend: Union[None, PubSubConnection] = None,
        app_name: Union[None, str] = None,
        queue_names: Union[None, list[str]] = None,
        default_queue: Union[None, str] = None,
    ):
        if not broker or not backend:
            raise ValueError("broker and backend must be provided")
        queue_names = queue_names if queue_names else ""
        default_queue = default_queue if default_queue else self.default_queue
        if isinstance(queue_names, str):
            queue_names = {x.strip() for x in queue_names.split(",") if x.strip()}
        if not queue_names:
            queue_names = [default_queue]

        app_name = app_name if app_name else "default"
        if app_name not in self.app_dict:
            celery_app = Celery(app_name)
            self.app_dict[app_name] = celery_app
            if app_name not in self.async_task_registry:
                self.async_task_registry[app_name] = {}
            router = CeleryTaskRouter(
                app_name,
                default_queue if default_queue else self.default_queue,
                self.async_task_registry[app_name],
            )
            celery_app.conf.update(
                default_queue=default_queue if default_queue else self.default_queue,
                task_acks_late=True,
                celery_task_acks_on_failure_or_timeout=True,
                task_reject_on_worker_lost=True,
                task_track_started=True,
                broker_url=broker.get_url(),
                broker_transport_options=broker.get_transport_options(),
                broker_connection_retry_on_startup=True,
                result_backend=backend.get_url(),
                result_backend_transport_options=backend.get_transport_options(),
                timezone="Europe/London",
                enable_utc=True,
                task_routes=(router.route_task,),
                result_expires=60 * 60,
                worker_cancel_long_running_tasks_on_connection_loss=True,
            )

            registry = self.async_task_registry[app_name]
            self.app_tasks[app_name] = OrderedDict()
            app_tasks = self.app_tasks[app_name]
            for task_name in registry:
                async_task: AsyncTaskDescription = registry[task_name]
                celery_task = celery_app.task(name=task_name, base=CeleryBaseTask)(
                    async_task.task_method
                )
                async_task.task_method = celery_task
                app_tasks[task_name] = celery_task
                logger.info(
                    "Task %s is registered to celery app '%s'", task_name, app_name
                )
        return self.app_dict[app_name]

    async def get_async_task(
        self,
        task_description: AsyncTaskDescription,
        id_generator: IdGenerator = None,
        **kwargs,
    ) -> AsyncTaskExecutor:
        app_name = self.app_name
        task_name = task_description.task_name

        if task_name not in self.app_tasks[app_name]:
            raise AsyncTaskError(f"Task {task_name} is not registered.")
        task = self.app_tasks[app_name][task_name]
        return CeleryAsyncTaskExecutor(
            task, task_name=task_name, id_generator=id_generator, **kwargs
        )

    async def get_async_task_result(self, task_id: str) -> AsyncTaskResult:
        if not task_id:
            raise ValueError(task_id)
        task = AsyncResult(task_id)
        if not task:
            raise AsyncTaskNotFoundError(task_id)
        return CeleryAsyncTaskResult(task)

    def run_chain(
        self,
        tasks: list[AsyncTaskExecutor],
        expires: Union[None, int] = None,
    ) -> AsyncTaskResult:
        job = group(chain([x.subtask(x.kwargs) for x in tasks]))
        task = job.apply_async(expires=expires)
        task_result = CeleryAsyncTaskResult(task, is_group=True)
        task_result.save()
        return task_result

    def run_group(
        self,
        tasks: list[AsyncTaskExecutor],
        expires: Union[None, int] = None,
    ) -> AsyncTaskResult:
        job = group([x.subtask(x.kwargs) for x in tasks])
        task = job.apply_async(expires=expires)
        task_result = CeleryAsyncTaskResult(task, is_group=True)
        task_result.save()
        return task_result
