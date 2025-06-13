import celery
from celery.utils.log import get_logger

from mhd_ws.application.context.request_tracker import (
    RequestTrackerModel,
    get_request_tracker,
)

logger = get_logger(__name__)


class CeleryBaseTask(celery.Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error("%s failed: %s", task_id, str(exc))

    def before_start(self, task_id, args, kwargs):
        request_tracker = get_request_tracker()
        request_tracker.task_id_var.set(task_id)
        if "request_tracker" in kwargs:
            request_tracker_dict = kwargs["request_tracker"]

            if request_tracker_dict:
                try:
                    if isinstance(request_tracker_dict, dict):
                        model = RequestTrackerModel.model_validate(request_tracker_dict)
                    else:
                        model = request_tracker_dict
                    if (
                        self.request
                        and self.request.headers
                        and "CORRELATION_ID" in self.request.headers
                        and self.request.headers["CORRELATION_ID"]
                    ):
                        correlation_id = self.request.headers["CORRELATION_ID"]
                        model.request_id = correlation_id
                    model.task_id = task_id
                    get_request_tracker().update_request_tracker(model)
                except LookupError:
                    logger.debug("lookup error for request.")
        else:
            get_request_tracker().reset_request_tracker()

    def run(self, *args, **kwargs):
        raise NotImplementedError()
