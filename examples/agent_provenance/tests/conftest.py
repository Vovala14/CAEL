"""Run actual engines/frameworks with outbound Python sockets disabled."""

import os
import socket
import threading
import traceback
from pathlib import Path

import pytest

os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ["CREWAI_TELEMETRY_ENABLED"] = "false"
os.environ["CREWAI_DISABLE_VERSION_CHECK"] = "true"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["ANONYMIZED_TELEMETRY"] = "false"


@pytest.fixture(scope="session")
def runtime():
    from cael_provenance import CAELRuntime

    return CAELRuntime(os.environ["CAEL040_ROOT"])


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    attempts = []
    creating_pair = threading.local()
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_pair = socket.socketpair

    def local_pair(*args, **kwargs):
        # Windows asyncio implements its local wakeup pipe using a stdlib
        # loopback socket pair. Permit only this synchronous IPC construction,
        # not arbitrary loopback clients or a local model/API endpoint.
        creating_pair.active = True
        try:
            return original_pair(*args, **kwargs)
        finally:
            creating_pair.active = False

    def reject(*args, **kwargs):
        detail = repr(args[1:] if args and isinstance(args[0], socket.socket) else args)
        trace = "".join(traceback.format_stack(limit=9))
        attempts.append(detail)
        raise AssertionError(
            "No network/model/API call is allowed: " + detail + "\n" + trace
        )

    def guarded_connect(sock, address):
        if (
            getattr(creating_pair, "active", False)
            and isinstance(address, tuple)
            and address[0] in ("127.0.0.1", "::1")
        ):
            return original_connect(sock, address)
        return reject(sock, address)

    def guarded_connect_ex(sock, address):
        if (
            getattr(creating_pair, "active", False)
            and isinstance(address, tuple)
            and address[0] in ("127.0.0.1", "::1")
        ):
            return original_connect_ex(sock, address)
        return reject(sock, address)

    monkeypatch.setattr(socket, "socketpair", local_pair)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)
    monkeypatch.setattr(socket, "create_connection", reject)
    yield
    assert not attempts


@pytest.fixture(scope="session")
def artifact_dir():
    path = Path(os.environ["CAEL_PROVENANCE_ARTIFACT_DIR"])
    path.mkdir(parents=True, exist_ok=True)
    return path
