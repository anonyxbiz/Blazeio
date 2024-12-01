# Dependencies.__init___.py
from asyncio import new_event_loop, run as io_run, CancelledError, get_event_loop, start_server as io_start_server, current_task, all_tasks, TimeoutError, wait_for, to_thread

from json import dumps, loads, JSONDecodeError
from sys import exit
from datetime import datetime as dt
from inspect import signature as sig
from typing import Callable

"""File serving"""
from aiofiles import open as iopen
from mimetypes import guess_type
from os.path import basename, getsize, exists, join

from gzip import compress as gzip_compress

p = print

from logging import StreamHandler, Formatter, getLogger, INFO

class GreenLogHandler(StreamHandler):
    def __init__(self, stream=None):
        super().__init__(stream)
        self.green = '\033[32m'  # ANSI escape code for green text
        self.reset = '\033[39m'  # Reset color to default
        self.setFormatter(Formatter('%(message)s'))

    def emit(self, record):
        try:
            msg = self.format(record)
            # Prefix the message with green color and reset it afterward
            self.stream.write(f"{self.green}{msg}{self.reset}\n")
        except Exception as e:
            self.handleError(record)

logger = getLogger('BlazeioLogger')
logger.setLevel(INFO)

green_handler = GreenLogHandler()
logger.addHandler(green_handler)

p = logger.info

class Log:
    known_exceptions = [
        "[Errno 104] Connection reset by peer",
        "Client has disconnected. Skipping write.",
        "Connection lost",
    ]

    @classmethod
    async def m(app, r, message):
        message = str(message).strip()
        
        if message in app.known_exceptions:
            return

        p(
            "{%s•%s} | [%s:%s] %s" % (
                r.identifier,
                str(r.connection_established_at),
                r.ip_host,
                str(r.ip_port),
                message
            )
        )

    @classmethod
    async def say(app, identifier: str, message):
        message = str(message).strip()

        p(
            "{%s•%s} | %s" % (
                identifier,
                str(dt.now()),
                message
            )
        )

class Err(Exception):
    def __init__(app, message=None):
        super().__init__(message)
        app.message = str(message)

    def __str__(app) -> str:
        return app.message

class ServerGotInTrouble(Exception):
    def __init__(app, message=None):
        super().__init__(message)
        app.message = str(message)

    def __str__(app) -> str:
        return app.message

class Packdata:
    @classmethod
    async def add(app, **kwargs):
        app = app()
        app.__dict__.update(**kwargs)
        return app

