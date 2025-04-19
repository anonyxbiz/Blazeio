# Dependencies.__init___.py
from asyncio import new_event_loop, run as io_run, CancelledError, get_event_loop, current_task, all_tasks, to_thread, sleep, gather, Protocol as asyncProtocol, run, create_subprocess_shell, set_event_loop, Event, BufferedProtocol, wait_for, TimeoutError, subprocess, iscoroutine, Queue as asyncQueue, run_coroutine_threadsafe, wrap_future, wait_for, ensure_future, Future as asyncio_Future, wait as asyncio_wait, FIRST_COMPLETED as asyncio_FIRST_COMPLETED

from collections import deque, defaultdict, OrderedDict

from sys import exit
from datetime import datetime as dt
from inspect import signature as sig, stack
from typing import Callable

from mimetypes import guess_type
from os import stat, kill, getpid, path, environ

from zlib import decompressobj, compressobj, MAX_WBITS as zlib_MAX_WBITS
from brotlicffi import Decompressor, Compressor, compress as brotlicffi_compress

from time import perf_counter, gmtime, strftime, strptime, sleep as timedotsleep

from threading import Thread, Event as ThreadEvent

try:
    from ujson import dumps, loads, JSONDecodeError
except:
    from json import dumps, loads, JSONDecodeError

from html import escape
from traceback import extract_tb, format_exc
from queue import Queue

from sys import stdout as sys_stdout

from collections.abc import AsyncIterable
from typing import Optional, Union

from ssl import create_default_context, SSLError, Purpose, CERT_NONE

from contextlib import asynccontextmanager

from psutil import Process as psutilProcess
from base64 import b64encode

from secrets import token_urlsafe

debug_mode = environ.get("BlazeioDev", None)

pid = getpid()
main_process = psutilProcess(pid)

INBOUND_CHUNK_SIZE, OUTBOUND_CHUNK_SIZE = 1024*100, 1024*100

class DotDict:
    def __init__(app, dictionary):
        app._dict = dictionary

    def __getattr__(app, name):
        if name in app._dict:
            return app._dict[name]

        raise AttributeError("'DotDict' object has no attribute '%s'" % name)

class Default_logger:
    colors = DotDict({
        'info': '\033[32m',
        'error': '\033[31m',
        'warning': '\033[33m',
        'critical': '\033[38;5;1m',
        'debug': '\033[34m',
        'reset': '\033[32m'
    })

    known_exceptions = (
        "[Errno 104] Connection reset by peer",
        "Client has disconnected.",
        "Connection lost",
        "asyncio/tasks.py",
    )

    def __init__(app, name=""):
        app.name = name
        app.logs = asyncQueue(maxsize=0)
        app.log_idle_event = Event()
        app.log_idle_event.set()

        app._thread = Thread(target=app.start, daemon=True)
        app._thread.start()

    def __getattr__(app, name):
        if name in app.colors._dict:
            async def dynamic_method(*args, **kwargs):
                return await app.__log__(app.colors.__getattr__(name), *args, **kwargs)

            setattr(app, name, dynamic_method)
            return dynamic_method

        raise AttributeError("'DefaultLogger' object has no attribute '%s'" % name)

    async def __log_actual__(app, color, log):
        if not isinstance(log, str):
            log = str(log)

        if not "\n" in log: log += "\n"
        sys_stdout.write("\r%s%s" % (color,log))

    async def __log__(app, *args, **kwargs):
        app.loop.call_soon_threadsafe(app.logs.put_nowait, (args, kwargs))

    async def log_worker(app):
        while True:
            args, kwargs = await app.logs.get()
            await app.__log_actual__(*args, **kwargs)

            if app.logs.empty():
                app.log_idle_event.set()
            else:
                app.log_idle_event.clear()
    
    async def flush(app):
        return await wrap_future(run_coroutine_threadsafe(app.log_idle_event.wait(), app.loop))

    def start(app):
        app.loop = new_event_loop()
        app.loop.run_until_complete(app.log_worker())

class Err(Exception):
    __slots__ = (
        'message',
    )
    def __init__(app, message=None):
        app.message = str(message)

    def __str__(app) -> str:
        return app.message

class ServerGotInTrouble(Exception):
    __slots__ = (
        'message',
    )
    def __init__(app, message=None):
        app.message = str(message)

    def __str__(app) -> str:
        return app.message

routines = {
    ("loop = get_event_loop()", "loop = None"),
    ("import uvloop", ""),
    ("uvloop.install()", ""),
    ("from aiofile import async_open", "async_open = NotImplemented"),
}

def routine_executor(arg):
    for if_, else_ in arg:
        try:
            exec(if_, globals())
        except Exception as e:
            e = str(e).strip()
            if not "uvloop" in e: print("routine_executor Exception: %s\n" % e)

            if else_ == NotImplemented:
                raise Err("A required package is not installed.")
            try:
                exec(else_, globals())
            except Exception as e:
                print("routine_executor Exception: %s\n" % str(e).strip())

routine_executor(routines)

class __log__:
    known_exceptions = (
        "[Errno 104] Connection reset by peer",
        "Client has disconnected.",
        "Connection lost",
        "asyncio/tasks.py",
    )

    def __init__(app): pass

    def __getattr__(app, name):
        if name in logger.colors._dict:
            async def dynamic_method(*args, **kwargs):
                return await app.__log__(*args, **kwargs, logger_=logger.__getattr__(name))
            
            setattr(app, name, dynamic_method)
            return dynamic_method

        raise AttributeError("'DefaultLogger' object has no attribute '%s'" % name)

    async def __log__(app, r=None, message=None, color=None, logger_=None):
        try:
            if "BlazeioServerProtocol" in str(r):
                message = str(message).strip()

                if message in app.known_exceptions:
                    return

                await logger_(
                    "%s•%s | [%s:%s] %s" % (
                        r.identifier,
                        str(dt.now()),
                        r.ip_host,
                        str(r.ip_port),
                        message
                    )
                )
            else:
                _ = str(r).strip()
                if message:
                    _ += message
                    
                message = _

                if message in app.known_exceptions:
                    return

                msg = message

                if msg == "":
                    await logger_(message)
                    return
                
                await logger_(
                    "%s•%s | %s" % (
                        "",
                        str(dt.now()),
                        message
                    )
                )
        except Exception as e:
            pass


logger = Default_logger(name='BlazeioLogger')

Log = __log__()

routine_executor({
    ('p = Log.info', 'p = None'),
    ('log = logger', 'p = None')
})