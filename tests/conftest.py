import socket
from typing import NoReturn

import pytest


class NetworkBlockedError(RuntimeError):
    """Raised when a test tries to open a network connection.

    A RuntimeError on purpose: code that catches OSError cannot swallow it.
    """


def _blocked(*args: object, **kwargs: object) -> NoReturn:
    raise NetworkBlockedError("network access is blocked in tests")


@pytest.fixture(autouse=True)
def _block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
