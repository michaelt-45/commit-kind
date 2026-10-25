"""Network guard shared by conftest and the tests (kept out of conftest on purpose)."""

import socket
from typing import NoReturn


class NetworkBlockedError(RuntimeError):
    """Raised when a test tries to open a network connection or resolve a name.

    A RuntimeError on purpose: code that catches OSError cannot swallow it.
    """


GUARDED_NAMES = (
    "socket",
    "create_connection",
    "getaddrinfo",
    "gethostbyname",
    "gethostbyname_ex",
)


def blocked(*args: object, **kwargs: object) -> NoReturn:
    raise NetworkBlockedError("network access is blocked in tests")


def install() -> dict[str, object]:
    """Replace the guarded socket functions; return the originals."""
    originals = {name: getattr(socket, name) for name in GUARDED_NAMES}
    for name in GUARDED_NAMES:
        setattr(socket, name, blocked)
    return originals


def restore(originals: dict[str, object]) -> None:
    for name, original in originals.items():
        setattr(socket, name, original)
