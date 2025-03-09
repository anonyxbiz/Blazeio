# Dependencies.__init___.py
from asyncio import new_event_loop, run as io_run, CancelledError, get_event_loop, current_task, all_tasks, to_thread, sleep, gather, Protocol as asyncProtocol, run, create_subprocess_shell, set_event_loop, Event, BufferedProtocol, wait_for, TimeoutError

from collections import deque, defaultdict, OrderedDict

from sys import exit
from datetime import datetime as dt
from inspect import signature as sig, stack
from typing import Callable

from mimetypes import guess_type
from os import stat, kill, getpid, path
from signal import SIGKILL

from gzip import compress as gzip_compress

from time import perf_counter, gmtime, strftime, strptime, sleep as timedotsleep

from threading import Thread
from multiprocessing import Process

from aiologger import Logger
from ujson import dumps, loads, JSONDecodeError

from html import escape

pid = getpid()
INBOUND_CHUNK_SIZE = 1024
OUTBOUND_CHUNK_SIZE = 1024

logger = Logger.with_default_handlers(name='BlazeioLogger')

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

class Log:
    known_exceptions = (
        "[Errno 104] Connection reset by peer",
        "Client has disconnected.",
        "Connection lost",
    )

    colors = {
        'info': '\033[32m',
        'error': '\033[31m',
        'warning': '\033[33m',
        'critical': '\033[38;5;1m',
        'debug': '\033[34m',
        'reset': '\033[32m'
    }

    @classmethod
    async def __log__(app, r=None, message=None, color=None, logger_=logger.info):
        try:
            log_level = logger_.__name__[logger_.__name__.rfind(".") + 1:]

            color = color or app.colors.get(log_level, app.colors['reset'])

            if "BlazeioPayload" in str(r):
                message = str(message).strip()

                if message in app.known_exceptions:
                    return

                message = f"{color}{message}{app.colors['reset']}"

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
                message = f"{color}{message}{app.colors['reset']}"

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

    @classmethod
    async def info(app, *args): await app.__log__(*args, logger_=logger.info)

    @classmethod
    async def error(app, *args): await app.__log__(*args, logger_=logger.error)

    @classmethod
    async def warning(app, *args): await app.__log__(*args, logger_=logger.warning)

    @classmethod
    async def critical(app, *args): await app.__log__(*args, logger_=logger.critical)

    @classmethod
    async def debug(app, *args): await app.__log__(*args, logger_=logger.debug)

    @classmethod
    async def m(app, *args): await app.__log__(*args, logger_=logger.error)

    @classmethod
    async def bench(app):
        start_time = dt.now().timestamp()

        async def w(task):
            for method in dir(app):
                method = getattr(app, method)
    
                if isinstance(method, Callable) and not (name := method.__name__).startswith((sepr := "__")) and not name.endswith(sepr) and method != app.bench and not name in ["type"]:
    
                    await method(None, name)
            
            await app.info("Task %s completed successfully in %s seconds" % (task, dt.now().timestamp() - start_time))

        tasks = []

        while len(tasks) < 500:
            task = loop.create_task( w(len(tasks) +1 ) )
            tasks.append(task)

        await gather(*tasks)

        exit()

class VersionControlla:
    @classmethod
    async def control(app, ins, HOME, HOST, PORT, **kwargs):
        async def runner():
            process = await create_subprocess_shell(
                cmd=f'python -m Blazeio --path "{HOME}" --host "{HOST}" --port "{PORT}"',
                stdout=None,
                stderr=None,
            )
            try:
                await process.wait()
            except CancelledError:
                process.terminate()
                await process.wait()
                raise

        while True:
            size = getsize(HOME)
            task = loop.create_task(runner())

            while True:
                if task.done():
                    break
                
                if getsize(HOME) == size:
                    await sleep(1)
                else:
                    await Log.warning(f"version change detected in {HOME}, reloading server...")
                    break
            
            if not task.done():
                try:
                    task.cancel()
                    await task
                except CancelledError:
                    pass

            else:
                break

routine_executor({
    ('p = Log.info', 'p = None'),
    ('loop.run_until_complete(Log.debug(""))', '')
})