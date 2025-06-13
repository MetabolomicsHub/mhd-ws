from typing import Any, Union

from starlette import authentication


class UnauthenticatedUser(authentication.BaseUser):
    def __init__(self):
        self._permission_context: Union[None, Any] = None

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
    def permission_context(self) -> Any:
        return self._permission_context

    @permission_context.setter
    def permission_context(self, value):
        self._permission_context = value


class AuthenticatedUser(authentication.BaseUser):
    def __init__(self, user: str):
        self._user: str = user
        self._full_name = f"{self._user.first_name} {self._user.last_name}"
        self._permission_context: Union[None, Any] = None

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self._full_name

    @property
    def identity(self) -> str:
        return self._user

    @property
    def user_detail(self) -> Any:
        return self._user

    @property
    def permission_context(self) -> Any:
        return self._permission_context

    @permission_context.setter
    def permission_context(self, value):
        self._permission_context = value
