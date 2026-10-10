"""Serve a Cressey app on a free local port, in a thread: for the eval and the tests."""

import socket
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager

import uvicorn
from fastapi import FastAPI


@contextmanager
def serve(app: FastAPI) -> Generator[str]:
    """The app's base URL while it runs."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(
        uvicorn.Config(app, log_level="warning", timeout_graceful_shutdown=1)
    )
    thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]})
    thread.start()
    for _ in range(500):
        if server.started:
            break
        time.sleep(0.01)
    else:
        raise RuntimeError("the Cressey server did not start")
    try:
        yield f"http://127.0.0.1:{sock.getsockname()[1]}"
    finally:
        server.should_exit = True
        thread.join(10)
