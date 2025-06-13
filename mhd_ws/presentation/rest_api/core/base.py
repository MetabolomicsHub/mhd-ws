from typing import TypeVar

from metabolights_utils.common import CamelCaseModel
from pydantic import ConfigDict
from pydantic.alias_generators import to_camel


class APIBaseModel(CamelCaseModel):
    """Base model class to convert python attributes to camel case"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


T = TypeVar("T", bound=CamelCaseModel)

L = TypeVar("L")
