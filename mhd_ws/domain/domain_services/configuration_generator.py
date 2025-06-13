from typing import Any, TypeVar

from mhd_ws.domain.component_configs.configuration import BaseConfiguration

T = TypeVar("T", bound=BaseConfiguration)


def create_config_from_dict(config_class: type[T], config_dict: dict[str, Any]) -> T:
    if not config_dict:
        raise ValueError(config_class.__name__, "Invalid input")
    return config_class.model_validate(config_dict)
