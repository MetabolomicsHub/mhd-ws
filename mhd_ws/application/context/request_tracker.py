from contextvars import ContextVar
from functools import lru_cache

from pydantic import BaseModel


class RequestTrackerModel(BaseModel):
    user_id: int = 0
    route_path: str = ""
    resource_id: str = ""
    client: str = ""
    request_id: str = ""
    task_id: str = ""


class RequestTracker:
    def __init__(self):
        self.user_id_var: ContextVar[int] = ContextVar("user_id")
        self.route_path_var: ContextVar[str] = ContextVar("route_path")
        self.resource_id_var: ContextVar[str] = ContextVar("resource_id")
        self.client_var: ContextVar[str] = ContextVar("client")
        self.request_id_var: ContextVar[str] = ContextVar("x_request_id")
        self.task_id_var: ContextVar[str] = ContextVar("task_id")
        self.reset_request_tracker()

    def update_request_tracker(self, request_tracker_update: RequestTrackerModel):
        self.user_id_var.set(request_tracker_update.user_id)
        self.resource_id_var.set(
            request_tracker_update.resource_id
            if request_tracker_update.resource_id
            else "-"
        )
        self.client_var.set(
            request_tracker_update.client if request_tracker_update.client else "-"
        )
        self.route_path_var.set(
            request_tracker_update.route_path
            if request_tracker_update.route_path
            else "-"
        )
        self.request_id_var.set(
            request_tracker_update.request_id
            if request_tracker_update.request_id
            else "-"
        )
        self.task_id_var.set(
            request_tracker_update.task_id if request_tracker_update.task_id else "-"
        )

    def reset_request_tracker(self):
        self.user_id_var.set(0)
        self.resource_id_var.set("-")
        self.client_var.set("-")
        self.route_path_var.set("-")
        self.request_id_var.set("-")
        self.task_id_var.set("-")

    def get_request_tracker_model(self) -> RequestTrackerModel:
        user_id = 0
        try:
            user_id = self.user_id_var.get()
        except LookupError:
            ...
        resource_id = "-"
        try:
            resource_id = self.resource_id_var.get()
        except LookupError:
            ...

        client = "-"
        try:
            client = self.client_var.get()
        except LookupError:
            ...

        route_path = "-"
        try:
            route_path = self.route_path_var.get()
        except LookupError:
            ...
        request_id = "-"
        try:
            request_id = self.request_id_var.get()
        except LookupError:
            ...
        task_id = "-"
        try:
            task_id = self.task_id_var.get()
        except LookupError:
            ...
        return RequestTrackerModel(
            user_id=user_id,
            route_path=route_path,
            resource_id=resource_id,
            client=client,
            request_id=request_id,
            task_id=task_id,
        )


REQUEST_TRACKER = RequestTracker()


@lru_cache
def get_request_tracker() -> RequestTracker:
    return REQUEST_TRACKER
