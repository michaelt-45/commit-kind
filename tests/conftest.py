import socket

import pytest

import _netguard

_originals: dict[str, object] = {}


def pytest_configure(config: pytest.Config) -> None:
    """Block the network for the whole session, including collection and wide-scope fixtures."""
    _originals.update(_netguard.install())


def pytest_unconfigure(config: pytest.Config) -> None:
    _netguard.restore(_originals)
    _originals.clear()


@pytest.fixture(autouse=True)
def _block_network() -> None:
    """Belt and braces: assert the guard is still installed before each test."""
    for name in _netguard.GUARDED_NAMES:
        assert getattr(socket, name) is _netguard.blocked
