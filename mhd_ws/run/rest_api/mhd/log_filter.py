from logging import Filter, LogRecord

from mhd_ws.application.context.request_tracker import (
    RequestTracker,
    get_request_tracker,
)


class DefaultLogFilter(Filter):
    filtered_module_names = {
        "celery.utils.functional",
        "multipart.multipart",
        "python_multipart.multipart",
        "httpcore.http11",
        "httpcore.connection",
    }

    filtered_routes = {
        "/summary",
        "/openapi.json",
        "/resources/favicon.ico",
        "/version",
    }

    def filter(
        self,
        record: LogRecord,
    ) -> bool:
        for module in self.filtered_module_names:
            if module in record.name:
                return False
        if (
            hasattr(record, "data")
            and record.data
            and "name" in record.data
            and record.data["name"] in self.filtered_module_names
        ):
            return False
        context_vars = get_request_tracker()

        if context_vars and isinstance(context_vars, RequestTracker):
            model = context_vars.get_request_tracker_model()
            record.user_id = model.user_id
            record.route_path = model.route_path
            record.resource_id = model.resource_id
            record.client = model.client
            record.request_id = model.request_id
            record.task_id = model.task_id
        else:
            record.user_id = 0
            record.route_path = "-"
            record.resource_id = "-"
            record.client = "-"
            record.request_id = "-"
            record.task_id = "-"
        for route in self.filtered_routes:
            if record.route_path.startswith(route):
                return False
        return True
