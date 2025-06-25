from typing import TypeVar

from pydantic import ConfigDict
from pydantic.alias_generators import to_camel

from mhd_ws.domain.shared.model import MhdBaseModel


class APIBaseModel(MhdBaseModel):
    """Base model class to convert python attributes to camel case"""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


T = TypeVar("T", bound=MhdBaseModel)

L = TypeVar("L")
