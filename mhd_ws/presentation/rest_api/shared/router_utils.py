import importlib
import os
import pkgutil
from logging import getLogger

from fastapi import FastAPI

import mhd_ws

logger = getLogger(__name__)


def find_routers(path: str):
    modules = []
    data = list(pkgutil.walk_packages([path]))

    if data:
        for module in data:
            if module:
                if module.ispkg:
                    modules.extend(find_routers(f"{path}/{module.name}"))
                else:
                    modules.append(module)
    return modules


def add_routers(application: FastAPI, root_path: str):
    modules = find_routers(root_path)
    for m in modules:
        path = str(mhd_ws.application_root_path)
        relative = m.module_finder.path.replace(path, "").lstrip(os.sep)
        module_name = f"{relative.replace(os.sep, '.')}.{m.name}"
        module = importlib.import_module(module_name)
        if hasattr(module, "router"):
            logger.info("Module loaded: %s", module_name)
            router = getattr(module, "router")
            application.include_router(router)
