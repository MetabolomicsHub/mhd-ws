import asyncio
import ctypes
import logging
import threading
from asyncio import Task
from typing import Any, Callable, OrderedDict, Union

from mhd_ws.application.context.async_task_registry import AsyncTaskRegistry
from mhd_ws.application.context.request_tracker import (
    RequestTrackerModel,
    get_request_tracker,
)
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
from mhd_ws.domain.exceptions.async_task import (
    AsyncTaskNotFoundError,
    AsyncTaskRemoteFailure,
)
from mhd_ws.domain.shared.async_task.async_task_description import AsyncTaskDescription

logger = logging.getLogger()


class ThreadingAsyncTaskResult(AsyncTaskResult):
    def __init__(self, async_task_results_dict, task_id: str, is_group: bool = False):
        super().__init__(task_id)
        self.thread = None
        self.is_group = is_group
        self.ready = False
        self.successful = False
        self.result = None
        self.status = "PENDING"
        self.async_task_results_dict = async_task_results_dict
        self.async_task_results_dict[self.id] = self

    def get(self, timeout: Union[None, int] = None):
        if timeout is not None:
            self.thread.join(timeout)
        else:
            self.thread.join()
        if self.thread.is_alive():
            raise TimeoutError(f"Task {self.id} is still running...")

        if self.successful:
            return self.result

        if isinstance(self.result, Exception):
            raise self.result

        raise AsyncTaskRemoteFailure(f"Task {self.id} error.")

    def is_ready(self) -> bool:
        return self.ready

    def is_successful(self) -> bool:
        return self.successful

    def save(self): ...

    def revoke(self, terminate: bool = True):
        if terminate and self.thread.is_alive():
            logger.info("Thread is still running. Trying to kill thread...")
            thread_id = self.thread.ident
            res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_long(thread_id), ctypes.py_object(SystemExit)
            )
            if res == 0:
                raise AsyncTaskRemoteFailure("Invalid thread ID")
            if res > 1:
                # If it returns more than 1, it means we accidentally affected more threads
                ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(thread_id), 0)
                raise AsyncTaskRemoteFailure("PyThreadState_SetAsyncExc failed")

        if self.id in self.async_task_results_dict:
            del self.async_task_results_dict[self.id]
            logger.debug("Task %s is deleted.", self.id)

    def get_status(self):
        return self.status


class ThreadingAsyncTaskExecutor(AsyncTaskExecutor):
    def __init__(
        self,
        task_method: Callable,
        task_name: str,
        async_task_results_dict: dict[str, AsyncTaskResult],
        id_generator=Union[None, IdGenerator],
        **kwargs,
    ):
        self.id_generator = id_generator if id_generator else IdGenerator()
        self.task_method = task_method
        self.kwargs = kwargs
        self.task_name = task_name
        self.async_task_results_dict = async_task_results_dict

    async def start(self, expires: Union[None, int] = None) -> AsyncTaskResult:
        task_id = self.id_generator.generate_unique_id()
        async_task = ThreadingAsyncTaskResult(self.async_task_results_dict, task_id)
        request_tracker = get_request_tracker().get_request_tracker_model().model_dump()
        self.kwargs["request_tracker"] = request_tracker

        async def run_task():
            try:
                logger.info("Task %s with id %s started.", self.task_name, task_id)
                async_task.status = "RUNNING"
                request_tracker = get_request_tracker()
                model = RequestTrackerModel.model_validate(
                    self.kwargs["request_tracker"]
                )
                model.task_id = task_id
                request_tracker.update_request_tracker(model)

                result = self.task_method(**self.kwargs)
                if isinstance(result, Task):
                    output = await result
                else:
                    output = result
                async_task.status = "SUCCESS"
                async_task.result = output
                async_task.ready = True
                async_task.successful = True
                logger.info(
                    "Task %s with %s completed successfully.", self.task_name, task_id
                )
            except Exception as e:
                logger.error("Task %s failed.", task_id)
                logger.exception(e)
                async_task.status = "FAILED"
                async_task.result = e
                async_task.ready = True
                async_task.successful = False

        def run():
            try:
                loop = asyncio.get_running_loop()
                if loop.is_running():
                    result = asyncio.ensure_future(run_task())
                else:
                    result = loop.run_until_complete(run_task())
            except RuntimeError:
                result = asyncio.run(run_task())
            return result

        try:
            thread = threading.Thread(target=run)
            async_task.thread = thread
            thread.start()
            # await run_task()
        except BaseException as ex:
            async_task.status = "FAILED"
            async_task.result = ex
            async_task.ready = True
            async_task.successful = False
        return async_task


class ThreadingAsyncTaskService(AsyncTaskService):
    def __init__(  # noqa: PLR0913
        self,
        broker: Union[None, PubSubConnection] = None,
        backend: Union[None, PubSubConnection] = None,
        app_name: Union[None, str] = None,
        queue_names: Union[None, set[str]] = None,
        default_queue: Union[None, str] = None,
        async_task_registry: Union[None, AsyncTaskRegistry] = None,
    ):
        if not app_name:
            app_name = "default"
        super().__init__(
            broker, backend, app_name, queue_names, default_queue, async_task_registry
        )
        self.async_task_results_dict: dict[str, AsyncTaskResult] = OrderedDict()
        self.app_tasks: dict[str, AsyncTaskDescription] = OrderedDict()
        self.app = self._create_async_app(
            broker=broker,
            backend=backend,
            app_name=app_name,
            default_queue=default_queue,
        )

    def _create_async_app(
        self,
        broker: Union[None, PubSubConnection] = None,
        backend: Union[None, PubSubConnection] = None,
        app_name: Union[None, str] = None,
        default_queue: Union[None, str] = None,
    ) -> Any:
        if app_name in self.async_task_registry:
            for task_name in self.async_task_registry[app_name]:
                async_task = self.async_task_registry[app_name][task_name]
                self.app_tasks[task_name] = async_task
                logger.info(
                    "Task %s is registered to background threading app '%s'",
                    task_name,
                    app_name,
                )

        return self

    async def get_async_task(
        self,
        task_description: AsyncTaskDescription,
        app_name: Union[None, str] = None,
        id_generator: IdGenerator = None,
        **kwargs,
    ) -> AsyncTaskExecutor:
        if task_description.task_name not in self.app_tasks:
            raise Exception(f"Task {task_description.task_name} is not registered.")

        return ThreadingAsyncTaskExecutor(
            task_method=self.app_tasks[task_description.task_name].task_method,
            task_name=task_description.task_name,
            async_task_results_dict=self.async_task_results_dict,
            id_generator=id_generator,
            **kwargs,
        )

    async def get_async_task_result(
        self,
        task_id: str,
    ) -> AsyncTaskResult:
        if task_id in self.async_task_results_dict:
            return self.async_task_results_dict[task_id]
        raise AsyncTaskNotFoundError(task_id)
