from typing import Callable


class AsyncTaskDescription:
    def __init__(self, task_method: Callable, task_name: str, queue: str):
        self.queue = queue
        self.task_method = task_method
        self.task_name = task_name

    def __call__(self, **kwds):
        self.task_method(**kwds)
