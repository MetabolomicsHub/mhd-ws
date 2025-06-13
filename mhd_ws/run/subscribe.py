import ast
import os
from pathlib import Path
from typing import Any, Sequence, Union

from dependency_injector.wiring import inject
from pydantic import BaseModel

import mhd
from mhd_ws import application_root_path
from mhd_ws.application.decorators.async_task import async_task


class ArgumentFilter(BaseModel):
    default: Any
    values: set[Any]


def to_module_name(app_path: Path, file_path: Path) -> str:
    return (
        str(file_path)
        .replace(str(app_path), "")
        .strip(os.sep)
        .replace(os.sep, ".")
        .removesuffix(".py")
    )


def find_injectable_modules() -> list[tuple[str, str]]:
    return find_decorated_modules(inject.__name__)


def find_decorated_modules(
    decorator_name: str, decorator_kwargs: Union[None, dict[str, ArgumentFilter]] = None
) -> list[tuple[str, str]]:
    app_path = str(application_root_path / Path(mhd.__name__))

    result: Union[None, dict[str, Any]] = find_decorator_in_package(
        app_path,
        decorator_name,
        decorator_kwargs=decorator_kwargs,
    )
    module_names = []
    if result:
        module_names = [
            (
                to_module_name(application_root_path, x),
                x,
            )
            for x in result
        ]
    return module_names


def find_async_task_modules(
    app_name: Union[None, str] = None,
    queue_names: Union[None, str, Sequence[str]] = None,
) -> list[tuple[str, str]]:
    default_app_name = "default"
    default_queue_name = "common"
    app_name = app_name if app_name else default_app_name
    queue_names = queue_names if queue_names else default_queue_name
    decorator_kwargs = {}
    if isinstance(queue_names, str):
        queue_names = {x.strip() for x in queue_names.split(",")}
    decorator_kwargs = {
        "queue": ArgumentFilter(default=default_queue_name, values=queue_names),
        "app_name": ArgumentFilter(default=default_app_name, values={app_name}),
    }
    return find_decorated_modules(async_task.__name__, decorator_kwargs)


def find_decorator_in_file(
    file_path: Path,
    decorator_name: str,
    decorator_kwargs=Union[None, dict[str, ArgumentFilter]],
):
    decorator_kwargs: dict[str, ArgumentFilter] = (
        decorator_kwargs if decorator_kwargs else {}
    )
    with file_path.open("r", encoding="utf-8") as f:
        file_content = f.read()

    # Parse the content of the file into an AST
    tree = ast.parse(file_content, filename=file_path)

    decorated_functions = []

    # Traverse the AST nodes to find decorated functions
    for node in ast.walk(tree):
        if not isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
            continue
        for decorator in node.decorator_list:
            if (
                isinstance(decorator, ast.Name)
                and hasattr(decorator, "id")
                and decorator.id == decorator_name
            ):
                decorated_functions.append(node.name)
            elif (
                isinstance(decorator, ast.Call)
                and hasattr(decorator.func, "id")
                and decorator.func.id == decorator_name
            ):
                keywords = {x.arg: x.value.value for x in decorator.keywords}
                keywords.update(
                    {
                        key: filter_.default
                        for key, filter_ in decorator_kwargs.items()
                        if key not in keywords
                    }
                )
                matched = True
                for key, filter_ in decorator_kwargs.items():
                    if keywords[key] not in filter_.values:
                        matched = False
                        break
                if matched:
                    decorated_functions.append(node.name)

    return decorated_functions


def find_decorator_in_package(
    package_path, decorator_name, decorator_kwargs=Union[None, dict[str, Any]]
):
    """
    Recursively searches through a package for functions decorated with a specific decorator.

    Args:

        package_path (str): Path to the package directory.
        decorator_name (str): The name of the decorator to search for.

    Returns:

        dict: Dictionary where keys are file paths and values are lists of function names using the decorator.
    """
    result = {}

    for root, _, files in os.walk(package_path):
        root_path = Path(root)
        for file in files:
            if file.endswith(".py"):  # Only process Python files
                file_path = root_path / Path(file)
                decorated_functions = find_decorator_in_file(
                    file_path, decorator_name, decorator_kwargs
                )
                if decorated_functions:
                    result[file_path] = decorated_functions

    return result
