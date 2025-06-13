import datetime
import decimal
from typing import Any

import pytz
from dateutil import parser


def validate_datetime(value: Any) -> datetime.datetime:
    if value is None:
        raise ValueError("Value cannot be None")
    val = value
    if isinstance(value, str):
        try:
            val = parser.parse(value)
        except ValueError:
            raise ValueError("Value is not a valid datetime string")

    if isinstance(val, datetime.datetime):
        if val.tzinfo is None:
            return pytz.utc.localize(val)
        return val.astimezone(pytz.utc)
    raise ValueError("Value is not a valid datetime object")


def validate_integer(value: Any) -> int:
    if value is None:
        raise ValueError("Value cannot be None")

    if isinstance(value, int) or isinstance(value, decimal.Decimal):
        return int(value)

    raise ValueError("Value is not a valid integer value")


def validate_bool(value: Any) -> bool:
    if value is None:
        return False

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return False if int(value) == 0 else True

    if isinstance(value, str):
        return True if value.islower() in ("true", "yes", "1") else False

    raise ValueError("Value is not a valid boolean value")
