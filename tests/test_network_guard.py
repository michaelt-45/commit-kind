import socket
import urllib.request

import pytest

from _netguard import NetworkBlockedError


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


def test_dns_lookup_raises() -> None:
    with pytest.raises(NetworkBlockedError):
        socket.getaddrinfo("localhost", 80)
    with pytest.raises(NetworkBlockedError):
        socket.gethostbyname("localhost")
    with pytest.raises(NetworkBlockedError):
        socket.gethostbyname_ex("localhost")


@pytest.fixture(scope="module")
def module_scoped_attempt() -> BaseException | None:
    try:
        socket.socket()
    except NetworkBlockedError as exc:
        return exc
    return None


def test_module_scoped_fixture_is_guarded(module_scoped_attempt: BaseException | None) -> None:
    assert isinstance(module_scoped_attempt, NetworkBlockedError)
