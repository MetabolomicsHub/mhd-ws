import datetime
from typing import Annotated

import annotated_types
from pydantic import BeforeValidator

from mhd_ws.domain.shared.model_validators import validate_datetime, validate_integer

UtcDatetime = Annotated[datetime.datetime, BeforeValidator(validate_datetime)]
Integer = Annotated[int, BeforeValidator(validate_integer)]
ZeroOrPositiveInt = Annotated[int, annotated_types.Ge(0)]
PositiveInt = Annotated[int, annotated_types.Ge(1)]
TokenStr = Annotated[str, annotated_types.MinLen(20), annotated_types.MaxLen(10000)]
TaskIdStr = Annotated[str, annotated_types.MinLen(20), annotated_types.MaxLen(500)]
