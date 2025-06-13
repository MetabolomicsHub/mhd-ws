from pydantic import BaseModel


class ModuleConfiguration(BaseModel):
    loaded_sub_package_names: list[str] = []
