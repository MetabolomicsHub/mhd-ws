import importlib
import logging
import sys
from typing import Union

from mhd_ws.run.config import ModuleConfiguration

logger = logging.getLogger()


def load_modules(
    modules, module_config: Union[None, ModuleConfiguration] = None
) -> list:
    if not module_config:
        return []
    async_task_modules = []
    for module_name, file_path in modules:
        if is_filtered(module_name, module_config):
            logger.debug("Module %s is skipped.", module_name)
            continue
        if module_name in sys.modules:
            async_task_modules.append(sys.modules[module_name])
        else:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            sys.modules[module_name] = module
            async_task_modules.append(module)
    return async_task_modules


def is_filtered(
    module_name: str, module_config: Union[None, ModuleConfiguration] = None
) -> bool:
    if not module_config:
        return False
    for selected_base_module in module_config.loaded_sub_package_names:
        if module_name.startswith(selected_base_module):
            return False
    return True
