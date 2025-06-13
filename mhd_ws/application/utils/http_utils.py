import json
import logging
from typing import Any, Union

import httpx

logger = logging.getLogger(__name__)


async def get_http_response(
    url: str, root_dict_key: Union[None, str] = None
) -> Union[Any, dict[str, Any]]:
    if not url:
        raise ValueError("url is required")

    url = url.rstrip("/")
    if not url:
        return {}

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=10)
            response_obj = json.loads(response.text)

        if not root_dict_key:
            return response_obj

        if (
            response_obj
            and root_dict_key in response_obj
            and response_obj[root_dict_key]
        ):
            return response_obj[root_dict_key]
    except Exception as ex:
        logger.error("Error call %s: %s", url, str(ex))

    return {}
