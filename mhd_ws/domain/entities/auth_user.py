from typing import Any

from starlette import authentication


class UnauthenticatedUser(authentication.BaseUser):
    def __init__(
        self,
        requested_resource: None | str = None,
    ):
        self._requested_resource: None | str = requested_resource

    @property
    def is_authenticated(self) -> bool:
        return False

    @property
    def display_name(self) -> str:
        return ""

    @property
    def identity(self) -> str:
        return ""

    @property
    def requested_resource(self) -> Any:
        return self._requested_resource


class AuthenticatedUser(authentication.BaseUser):
    def __init__(
        self,
        name: str,
        requested_resource: None | str = None,
        resource_owner: None | bool = None,
    ):
        self.name: str = name
        self._requested_resource: None | str = requested_resource
        self._resource_owner: None | bool = resource_owner

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def identity(self) -> str:
        return self.name

    @property
    def user_detail(self) -> Any:
        return self.name

    @property
    def requested_resource(self) -> Any:
        return self._requested_resource

    @property
    def resource_owner(self) -> None | bool:
        return self._resource_owner
