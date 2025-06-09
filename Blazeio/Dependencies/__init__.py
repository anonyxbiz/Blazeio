# Dependencies.__init___.py
from ..Itools import *
from ..Exceptions import *
from ..Protocols import *
from asyncio import new_event_loop, run as io_run, CancelledError, get_event_loop, current_task, all_tasks, to_thread, sleep, gather, create_subprocess_shell, Event, BufferedProtocol, wait_for, TimeoutError, subprocess, Queue as asyncQueue, run_coroutine_threadsafe, wrap_future, wait_for, ensure_future, Future as asyncio_Future, wait as asyncio_wait, FIRST_COMPLETED as asyncio_FIRST_COMPLETED, Condition, iscoroutinefunction, iscoroutine, InvalidStateError

from subprocess import run as sb_run, PIPE
from collections import deque, defaultdict, OrderedDict
from collections.abc import AsyncIterable

from sys import exit, stdout as sys_stdout
from datetime import datetime as dt, UTC, timedelta

from inspect import signature as sig, stack
from typing import Callable, Any, Optional, Union

from mimetypes import guess_type
from os import stat, kill, getpid, path, environ, name as os_name

from os import path as os_path
from time import perf_counter, gmtime, strftime, strptime, sleep as timedotsleep

from threading import Thread
from html import escape

from traceback import extract_tb, format_exc
from ssl import create_default_context, Purpose, PROTOCOL_TLS_SERVER, OP_NO_SSLv2, OP_NO_SSLv3, OP_NO_TLSv1, OP_NO_TLSv1_1, OP_NO_COMPRESSION, CERT_NONE, SSLError

from contextlib import asynccontextmanager
from base64 import b64encode, b64decode

from string import ascii_lowercase as string_ascii_lowercase, ascii_uppercase as string_ascii_uppercase

from zlib import decompressobj, compressobj, MAX_WBITS as zlib_MAX_WBITS
from brotlicffi import Decompressor, Compressor, compress as brotlicffi_compress

from psutil import Process as psutilProcess

try: from ujson import dumps, loads, JSONDecodeError
except: from json import dumps, loads, JSONDecodeError

debug_mode = environ.get("BlazeioDev", None)

main_process = psutilProcess(pid := getpid())

class __ioConf__:
    __slots__ = ("INBOUND_CHUNK_SIZE", "OUTBOUND_CHUNK_SIZE", "url_to_host", "gen_payload", "url_decode_sync", "url_encode_sync", "get_params_sync", "loop", "headers_to_http_bytes", "ServerConfig",)

    def __init__(app):
        for bound in ("INBOUND_CHUNK_SIZE", "OUTBOUND_CHUNK_SIZE"):
            setattr(app, bound, 102400)

        for key in app.__slots__:
            if getattr(app, key, False) == False: setattr(app, key, None)

    def run(app, coro):
        return app.loop.run_until_complete(coro)

ioConf = __ioConf__()

def c_extension_importer():
    try:
        from c_request_util import url_decode_sync, url_encode_sync, get_params_sync
        from client_payload_gen import gen_payload
        from Blazeio_iourllib import url_to_host

        for i in (url_decode_sync, url_encode_sync, get_params_sync, gen_payload, url_to_host): setattr(ioConf, i.__name__, i)
    except ImportError as e:
        print(e)

c_extension_importer()

class SharpEvent:
    __slots__ = ("_set", "_waiters", "loop", "auto_clear")
    def __init__(app, auto_clear: bool = True, evloop = None):
        app._set, app._waiters, app.loop, app.auto_clear = False, [], evloop or get_event_loop(), auto_clear

    def is_set(app):
        return app._set
    
    def fut_done(app, fut):
        if fut.__is_cleared__: return
        fut.__is_cleared__ = True
        if app.auto_clear: app.clear()

    def done_callback_orchestrator(app, fut):
        for callback in fut.__acallbacks__:
            callback(fut)

    def add_done_callback(app, callback: callable):
        fut = app.get_fut()
        if callback in fut.__acallbacks__: return
        fut.__acallbacks__.append(callback)

    def get_fut(app):
        if app._waiters:
            return app._waiters[0]

        app._waiters.append(fut := app.loop.create_future())
        fut.__is_cleared__ = False
        fut.__acallbacks__ = [app.fut_done]
        fut.add_done_callback(app.done_callback_orchestrator)

        return fut

    async def wait(app):
        if app._set: return True
        return await app.get_fut()

    def clear(app):
        app._set = False

    def set(app, item = True):
        app._set = True

        if len(app._waiters) == 1:
            if not app._waiters[0].done(): app._waiters[0].set_result(item)
        else:
            for fut in app._waiters:
                if not fut.done(): fut.set_result(item)

        app._waiters.clear()

SharpEventManual = lambda auto_clear = False: SharpEvent(auto_clear=auto_clear)

class Enqueue:
    __slots__ = ("queue", "queue_event", "queue_add_event", "maxsize", "queueunderflow",)
    def __init__(app, maxsize: int = 100):
        app.maxsize = maxsize
        app.queue: deque = deque()
        app.queue_event: SharpEvent = SharpEvent()
        app.queue_add_event: SharpEvent = SharpEvent()
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
        'reset': '\033[32m',
        'yellow': '\033[33m',
        'blue': '\033[34m',
        'magenta': '\033[35m',
        'cyan': '\033[36m',
        'white': '\033[37m',
        'green': '\033[32m',
        'red': '\033[38;5;1m',
        'gray': '\033[90m',
        'b_red': '\033[91m',
        'b_green': '\033[92m',
        'b_yellow': '\033[93m',
        'b_blue': '\033[94m',
        'b_magenta': '\033[95m',
        'b_cyan': '\033[96m',
        'b_white': '\033[97m'
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

        if not log.startswith("\\"):
            prec = "\r"
        else:
            prec = ""

        sys_stdout.write("%s%s%s" % (prec, color, log))

    async def __log__(app, *args, **kwargs):
        await wrap_future(run_coroutine_threadsafe(app.logs.put((args, kwargs)), app.loop))

    async def loop_setup(app):
        app.logs = Enqueue(maxsize=app.maxsize)
        app.log_idle_event = SharpEvent()
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
        if app.logs.queue: return await wrap_future(run_coroutine_threadsafe(app.log_idle_event.wait(), app.loop))

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

routines = {
    ("loop = get_event_loop()", "loop = None"),
    ("import uvloop", ""),
    ("uvloop.install()", ""),
    ("from aiofile import async_open", "async_open = NotImplemented")
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

ioConf.loop = loop

class __log__:
    known_exceptions = ()

    def __init__(app): pass

    def __getattr__(app, name):
        if name in logger.colors._dict:
            async def dynamic_method(*args, **kwargs):
                return await app.__log__(*args, **kwargs, logger_=logger.__getattr__(name))

            setattr(app, name, dynamic_method)
            return dynamic_method

        raise AttributeError("'DefaultLogger' object has no attribute '%s'" % name)

    async def __log__(app, r=None, message=None, color=None, logger_=None, **kwargs):
        try:
            if isinstance(r, BlazeioProtocol):
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

                msg = message

                if msg == "":
                    await logger_(message, **kwargs)
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
    __slots__ = ("terminate", "Monitoring_thread", "event_loop", "Monitoring_thread_loop", "ServerConfig", "current_task",)

    def __init__(app):
        app.terminate = False
        app.event_loop = loop
        app.current_task = None

    def Monitoring_thread_join(app):
        app.terminate = True
        if app.current_task is not None: app.current_task.cancel()

    def Monitoring_thread_monitor(app, parent=None):
        app.Monitoring_thread_loop = new_event_loop()
        parent.on_exit_middleware(app.Monitoring_thread_join)

        app.Monitoring_thread_loop.run_until_complete(app.__monitor_loop__())

    async def __monitor_loop__(app):
        while not app.terminate:
            app.current_task = await wrap_future(run_coroutine_threadsafe(app.analyze_protocols(), app.event_loop))

            app.current_task = await sleep(app.ServerConfig.__timeout_check_freq__)

    async def enforce_health(app, Payload, task):
        if Payload.transport.is_closing():
            await app.cancel(Payload, task, "BlazeioHealth:: Task [%s] diconnected." % task.get_name())
            return True

    async def cancel(app, Payload, task, msg: (None, str) = None):
        try: task.cancel()
        except CancelledError: pass
        except KeyboardInterrupt: raise
        except Exception as e: await Log.warning("Blazeio", str(e))

        if msg: await Log.warning(Payload, msg)

    async def inspect_task(app, task):
        coro = task.get_coro()
        args = coro.cr_frame
        if args is None: return
        else: args = args.f_locals

        if not (Payload := args.get("app")): return

        if not isinstance(Payload, BlazeioProtocol): return

        if not hasattr(Payload, "__slots__"): return

        if not hasattr(Payload, "__perf_counter__"):
            if not "__perf_counter__" in Payload.__slots__: return
            Payload.__perf_counter__ = perf_counter()

        if await app.enforce_health(Payload, task): return

        duration = float(perf_counter() - getattr(Payload, "__perf_counter__"))

        timeout = float(Payload.__timeout__ or app.ServerConfig.__timeout__)

        condition = duration >= timeout

        if condition: await app.cancel(Payload, task, "BlazeioTimeout:: Task [%s] cancelled due to Timeout exceeding the limit of (%s), task took (%s) seconds." % (task.get_name(), str(timeout), str(duration)))

    async def analyze_protocols(app):
        for task in all_tasks(loop=app.event_loop):
            if task is not current_task():
                try: await app.inspect_task(task)
                except AttributeError: pass
                except KeyboardInterrupt: raise
                except Exception as e: await Log.critical(e)

ReMonitor = __ReMonitor__()
