from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    @classmethod
    def get_field_alias(cls, name: str) -> str:
        alias_exceptions = cls.get_field_alias_exceptions()
        if name in alias_exceptions:
            return alias_exceptions[name]
        return name

    @classmethod
    def get_field_alias_exceptions(cls):
        return {}
