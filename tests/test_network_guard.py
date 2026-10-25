import socket
import urllib.request

import pytest

from conftest import NetworkBlockedError


def test_socket_constructor_raises() -> None:
    with pytest.raises(NetworkBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def test_create_connection_raises() -> None:
    with pytest.raises(NetworkBlockedError):
        socket.create_connection(("127.0.0.1", 9), timeout=0.1)


def test_urllib_cannot_reach_network() -> None:
    with pytest.raises(NetworkBlockedError):
        urllib.request.urlopen("http://127.0.0.1:9", timeout=0.1)


def test_guard_error_message() -> None:
    with pytest.raises(NetworkBlockedError, match="network access is blocked"):
        socket.socket()
