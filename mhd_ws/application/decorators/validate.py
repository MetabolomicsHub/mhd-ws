from typing import Any, Callable, TypeVar

from pydantic import ConfigDict, validate_call

AnyCallableT = TypeVar("AnyCallableT", bound=Callable[..., Any])


def validate_inputs() -> Callable[[AnyCallableT], AnyCallableT]:
    return validate_call(
        validate_return=False,
        config=ConfigDict(
            strict=True,
            arbitrary_types_allowed=True,
        ),
    )


def validate_inputs_outputs(
    func: AnyCallableT,
) -> Callable[[AnyCallableT], AnyCallableT]:
    return validate_call(
        func,
        validate_return=True,
        config=ConfigDict(
            strict=True,
            arbitrary_types_allowed=True,
        ),
    )
