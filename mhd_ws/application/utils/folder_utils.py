import datetime
import logging
from typing import Union

logger = logging.getLogger(__name__)


def create_audit_folder_name(
    folder_suffix: Union[None, str] = "BACKUP",
    folder_prefix: Union[None, str] = None,
    timestamp_format: str = "%Y-%m-%d_%H-%M-%S",
) -> Union[None, str]:
    if not timestamp_format:
        logger.error("Invalid timestamp_format parameter.")
        raise ValueError("Invalid timestamp_format parameter.")
    base = datetime.datetime.now(datetime.timezone.utc).strftime(timestamp_format)
    folder_name = f"{base}_{folder_suffix}" if folder_suffix else base
    return f"{folder_prefix}_{folder_name}" if folder_prefix else folder_name
