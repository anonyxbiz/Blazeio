# Dependencies.__init___.py
from asyncio import new_event_loop, run as io_run, CancelledError, get_event_loop, current_task, all_tasks, to_thread, sleep, gather, Protocol as asyncProtocol, run, create_subprocess_shell, set_event_loop, Event, BufferedProtocol, wait_for, TimeoutError, subprocess, iscoroutine, Queue as asyncQueue, run_coroutine_threadsafe, wrap_future, wait_for, ensure_future, Future as asyncio_Future, wait as asyncio_wait, FIRST_COMPLETED as asyncio_FIRST_COMPLETED, Condition

from collections import deque, defaultdict, OrderedDict

from sys import exit
from datetime import datetime as dt
from inspect import signature as sig, stack
from typing import Callable

from mimetypes import guess_type
from os import stat, kill, getpid, path, environ
os_path = path

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

class __ioConf__:
    __slots__ = ("INBOUND_CHUNK_SIZE", "OUTBOUND_CHUNK_SIZE")

    def __init__(app):
        app.INBOUND_CHUNK_SIZE: int = 102400
        app.OUTBOUND_CHUNK_SIZE: int = 102400

ioConf = __ioConf__()

INBOUND_CHUNK_SIZE, OUTBOUND_CHUNK_SIZE = ioConf.INBOUND_CHUNK_SIZE, ioConf.OUTBOUND_CHUNK_SIZE

class DotDict:
    __slots__ = ("_dict",)
    def __init__(app, dictionary: (dict, None) = None):
        app._dict = dictionary or {}

    def __getattr__(app, name):
        if name in app._dict:
            return app._dict[name]
        else:
            return getattr(app._dict, name)

    def __contains__(app, key):
        if key in app._dict:
            return True
        return False

    def __setitem__(app, key, value):
        app._dict[key] = value

    def __setattr__(app, key, value):
        if key in app.__slots__:
            object.__setattr__(app, key, value)
        else:
            app._dict[key] = value

    def __getitem__(app, key):
        return app._dict[key]

    async def token_urlsafe(app, *args, **kwargs):
        while (token := token_urlsafe(*args, **kwargs)) in app._dict:
            await sleep(0)

        app._dict[token] = None
        return token

class Simple:
    @classmethod
    def Event(app, cleared = True):
        event = DotDict()
        event.event = Event()

        event.set = lambda evt = event.event: evt.set() != evt.clear()

        for i in ("clear", "wait", "is_set", "_waiters"):
            if callable(attr := getattr(event.event, i)):
                setattr(event, i, lambda attr=attr, *a, **k: attr(*a, **k))
            else:
                setattr(event, i, lambda attr=attr: attr)

        event.clear() if cleared else event.set()
        return event

class Sharpevent:
    __slots__ = ("event",)
    def __init__(app):
        app.event = Event()

    def __getattr__(app, name): return getattr(app.event, name)

    def is_set(app): return app.event.is_set()

    def wait(app): return app.event.wait()

    def set(app):
        app.event.set()
        app.event.clear()

class Enqueue:
    __slots__ = ("queue", "queue_event", "queue_add_event", "maxsize", "queueunderflow",)
    def __init__(app, maxsize: int = 100):
        app.maxsize = maxsize
        app.queue: deque = deque()
        app.queue_event: Sharpevent = Sharpevent()
        app.queue_add_event: Sharpevent = Sharpevent()
        app.queueunderflow: Condition = Condition()
        get_event_loop().create_task(app.check_overflow())

    async def check_overflow(app):
        while True:
            if len(app.queue) <= app.maxsize:
                async with app.queueunderflow:
                    app.queueunderflow.notify(app.maxsize - len(app.queue))

            await app.queue_event.wait()

    def available(app):
        return len(app.queue) <= app.maxsize

    def append(app, item, appendtype: deque):
        appendtype(item)
        app.queue_event.set()
        app.queue_add_event.set()

    def popleft(app):
        item = app.queue.popleft()
        app.queue_event.set()
        return item

    async def get_one(app, pop=True):
        if not app.queue:
            await app.queue_add_event.wait()
        if pop: return app.popleft()

    async def put(app, item, notify: bool = True, prioritize: bool = False):
        async with app.queueunderflow:
            appendtype = app.queue.append if not prioritize else app.queue.appendleft

            app.queue_event.set()
            await app.queueunderflow.wait()

            app.append(item, appendtype) if notify else app.append(item, appendtype)

    async def get(app):
        while True:
            await app.queue_add_event.wait()
            while app.queue: yield app.queue.popleft()

    def put_nowait(app, item):
        app.queue.append(item)
        app.queue_event.set()
        app.queue_add_event.set()

    def empty(app):
        return len(app.queue) <= 0

class Default_logger:
    colors: DotDict = DotDict({
        'info': '\033[32m',
        'error': '\033[31m',
        'warning': '\033[33m',
        'critical': '\033[38;5;1m',
        'debug': '\033[34m',
        'reset': '\033[32m'
    })

    known_exceptions: tuple = ("[Errno 104] Connection reset by peer", "Client has disconnected.", "Connection lost", "asyncio/tasks.py",)

    def __init__(app, name: str = "", maxsize: int = 1000, max_unflushed_logs: int = 100):
        app.name: str = name
        app.maxsize: int = maxsize
        app.max_unflushed_logs: int = max_unflushed_logs

        app._thread = Thread(target=app.start, daemon=True)
        app._thread.start()

    def __getattr__(app, name):
        if name in app.colors._dict:
            async def dynamic_method(*args, **kwargs):
                return await app.__log__(app.colors.__getattr__(name), *args, **kwargs)

            setattr(app, name, dynamic_method)
            return dynamic_method

        raise AttributeError("'DefaultLogger' object has no attribute '%s'" % name)

    async def __log_actual__(app, color, log, add_new_line = True):
        if not isinstance(log, str):
            log = str(log)

        if add_new_line and not "\n" in log: log += "\n"

        sys_stdout.write("\r%s%s" % (color,log))

    async def __log__(app, *args, **kwargs):
        await wrap_future(run_coroutine_threadsafe(app.logs.put((args, kwargs)), app.loop))

    async def loop_setup(app):
        app.logs = Enqueue(maxsize=app.maxsize)
        app.log_idle_event = Sharpevent()
        app.log_idle_event.set()
        app.loop.create_task(app.flush_dog())

    async def log_worker(app):
        await app.loop_setup()

        while True:
            await app.logs.get_one(pop=False)
            while app.logs.queue:
                args, kwargs = app.logs.popleft()
                await app.__log_actual__(*args, **kwargs)

            if not app.logs.queue:
                app.log_idle_event.set()
            else:
                app.log_idle_event.clear()

    async def flush(app):
        return await wrap_future(run_coroutine_threadsafe(app.log_idle_event.wait(), app.loop))
    
    async def flush_dog(app):
        unflushed_logs: int = 0
        while True:
            await app.logs.queue_add_event.wait()
            unflushed_logs += 1

            if unflushed_logs >= app.max_unflushed_logs:
                unflushed_logs = 0
                sys_stdout.flush()

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

class __ReMonitor__:
    __slots__ = ("terminate", "Monitoring_thread", "event_loop", "Monitoring_thread_loop", "ServerConfig", "client_queue",)

    def __init__(app):
        app.terminate = False
        app.client_queue = Enqueue()

    def Monitoring_thread_join(app):
        app.terminate = True

    def Monitoring_thread_monitor(app, parent=None):
        app.Monitoring_thread_loop = new_event_loop()
        parent.on_exit_middleware(app.Monitoring_thread_join)

        app.Monitoring_thread_loop.run_until_complete(app.__monitor_loop__())

    async def __monitor_loop__(app):
        # run_coroutine_threadsafe(app.check_client_protocol(None), app.event_loop)

        while not app.terminate:
            await wrap_future(run_coroutine_threadsafe(app.check_server_protocol(), app.event_loop))
            await sleep(app.ServerConfig.__timeout_check_freq__)

    async def check_client_protocol(app, Payload=None):
        if not Payload:
            while True:
                len_ = len(app.client_queue.queue)
                count = 0
                async for Payload in app.client_queue.get():
                    count += 1
                    await app.check_client_protocol(Payload)
                    if count >= len_: break
                await sleep(app.ServerConfig.__timeout_check_freq__)
            return

        duration = float(perf_counter() - getattr(Payload, "__perf_counter__"))

        timeout = float(Payload.__timeout__ or app.ServerConfig.__timeout__)

        condition = duration >= timeout

        if Payload.transport.is_closing(): Payload.__evt__.set()

        elif condition:
            await Log.critical("BlazeioTimeout:: Task [%s:%s] cancelled due to Timeout exceeding the limit of (%s), task took (%s) seconds." % (Payload.transport.get_extra_info("peername"), str(timeout), str(duration)))
            Payload.transport.close()
            Payload.__evt__.set()
        else:
            pass#app.client_queue.put_nowait(Payload)

    async def enforce_health(app, Payload, task):
        if Payload.transport.is_closing():
            await app.cancel(Payload, task, "BlazeioHealth:: Task [%s] diconnected." % task.get_name())
            return True

    async def cancel(app, Payload, task, msg: str = ""):
        try: task.cancel()
        except CancelledError: pass
        except KeyboardInterrupt as e: raise e
        except Exception as e: await Log.warning("Blazeio", str(e))

        if msg != "": await Log.warning(Payload, msg)

    async def inspect_task(app, task):
        coro = task.get_coro()
        args = coro.cr_frame
        if args is None: return
        else: args = args.f_locals

        if not (Payload := args.get("app")): return

        if not "BlazeioServerProtocol" in str(Payload): return

        if not hasattr(Payload, "__slots__"): return

        if not hasattr(Payload, "__perf_counter__"):
            if not "__perf_counter__" in Payload.__slots__: return
            Payload.__perf_counter__ = perf_counter()

        if await app.enforce_health(Payload, task): return

        duration = float(perf_counter() - getattr(Payload, "__perf_counter__"))

        timeout = float(Payload.__timeout__ or app.ServerConfig.__timeout__)

        condition = duration >= timeout

        if condition: await app.cancel(Payload, task, "BlazeioTimeout:: Task [%s] cancelled due to Timeout exceeding the limit of (%s), task took (%s) seconds." % (task.get_name(), str(timeout), str(duration)))

    async def check_server_protocol(app):
        for task in all_tasks(loop=app.event_loop):
            if task is not current_task():
                try:
                    await app.inspect_task(task)
                except AttributeError:
                    pass
                except KeyboardInterrupt as e: raise e
                except Exception as e:
                    await Log.critical(e)

ReMonitor = __ReMonitor__()
