# Dependencies.__init___.py
from ..Itools import *
from ..Exceptions import *
from ..Protocols import *
from asyncio import new_event_loop, set_event_loop, set_event_loop_policy, run as io_run, CancelledError, get_event_loop, current_task, all_tasks, to_thread, sleep, gather, create_subprocess_shell, Event, BufferedProtocol, wait_for, TimeoutError, subprocess, Queue as asyncQueue, run_coroutine_threadsafe, wrap_future, wait_for, ensure_future, Future as asyncio_Future, wait as asyncio_wait, FIRST_COMPLETED as asyncio_FIRST_COMPLETED, Condition, iscoroutinefunction, iscoroutine, InvalidStateError

from socket import socket, AF_INET, SOCK_STREAM, SOL_SOCKET, SO_REUSEPORT, IPPROTO_TCP, TCP_NODELAY, SHUT_RDWR, SO_REUSEADDR

from subprocess import run as sb_run, PIPE
from collections import deque, defaultdict, OrderedDict
from collections.abc import AsyncIterable

from sys import exit, stdout as sys_stdout
from sys import _getframe
from datetime import datetime as dt, UTC, timedelta

from inspect import signature as sig, stack
from typing import Callable, Any, Optional, Union

from mimetypes import guess_type
from os import stat, kill, getpid, path, environ, name as os_name, getcwd

from os import path as os_path
from time import perf_counter, gmtime, strftime, strptime, sleep as timedotsleep

from threading import Thread, Lock as T_lock, Event as Tevent
from html import escape

from traceback import extract_tb, format_exc
from ssl import create_default_context, Purpose, PROTOCOL_TLS_SERVER, OP_NO_SSLv2, OP_NO_SSLv3, OP_NO_TLSv1, OP_NO_TLSv1_1, OP_NO_COMPRESSION, CERT_NONE, SSLError

from contextlib import asynccontextmanager
from base64 import b64encode, b64decode

from string import ascii_lowercase as string_ascii_lowercase, ascii_uppercase as string_ascii_uppercase

from zlib import decompressobj, compressobj, MAX_WBITS as zlib_MAX_WBITS
from brotlicffi import Decompressor, Compressor, compress as brotlicffi_compress

from psutil import Process as psutilProcess

try:
    from ujson import dumps as ujson_dumps, loads, JSONDecodeError
    dumps = lambda *args, indent = 4, reject_bytes = False, escape_forward_slashes = False, **kwargs: ujson_dumps(*args, indent = indent, reject_bytes = reject_bytes, escape_forward_slashes = escape_forward_slashes, **kwargs)
except:
    from json import dumps, loads, JSONDecodeError

debug_mode = environ.get("BlazeioDev", None)

main_process = psutilProcess(pid := getpid())

class __ioConf__:
    def __init__(app, **kwargs):
        app.add(shutdown_callbacks = [])
        app.add(default_http_server_config = {
            "__http_request_heading_end_seperator__": b"\r\n\r\n",
            "__http_request_heading_end_seperator_len__": 4,
            "__http_request_max_buff_size__": 102400,
            "__http_request_initial_separatir__": b' ',
            "__http_request_auto_header_parsing__": True,
            "funcname_normalizers": {
                "_": "/"
            }
        })
        app.add(**kwargs)

    def __getattr__(app, key, default = None):
        return default

    def add(app, **kwargs):
        for key in kwargs:
            setattr(app, key, kwargs[key])

    def run(app, coro):
        return app.loop.run_until_complete(coro)

    def new_event_loop(app):
        app.loop = new_event_loop()
        set_event_loop(app.loop)
        globals()["loop"] = app.loop
        return app.loop

    def get_event_loop(app):
        if app.loop: return app.loop
        app.loop = get_event_loop()
        set_event_loop(app.loop)
        globals()["loop"] = app.loop
        return app.loop

    def add_shutdown_callback(app, cb, *args, **kwargs):
        app.shutdown_callbacks.append((cb, args, kwargs))

    def run_callbacks(app):
        for cb, args, kwargs in app.shutdown_callbacks:
            if iscoroutinefunction(cb):
                app.loop.create_task(cb(*args, **kwargs))
            elif iscoroutine(cb):
                app.loop.create_task(cb, *args, **kwargs)
            else:
                cb(*args, **kwargs)

    def event_wait_clear(app, event, *args, **kwargs):
        event.wait(*args, **kwargs)
        return event.clear()

ioConf = __ioConf__(INBOUND_CHUNK_SIZE = 102400, OUTBOUND_CHUNK_SIZE = 102400)

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

    async def wait_clear(app):
        await app.wait()
        return app.clear()

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
    __slots__ = ("queue", "queue_event", "queue_add_event", "maxsize", "queueunderflow", "loop")
    def __init__(app, maxsize: int = 100, evloop = None, cond = None):
        app.maxsize = maxsize
        app.loop = evloop or get_event_loop()
        app.queue: deque = deque()
        app.queue_event: SharpEvent = SharpEvent(evloop = app.loop)
        app.queue_add_event: SharpEvent = SharpEvent(evloop = app.loop)
        app.queueunderflow = cond(evloop = app.loop) if cond else Condition()
        app.loop.create_task(app.check_overflow())

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
        app.wakeup()

    def wakeup(app):
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
        'grey': '\033[90m',
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
    def __init__(app, name: str = "", maxsize: int = 1000):
        ioConf.add_shutdown_callback(app.stop)
        app.name = name
        app.maxsize = maxsize
        app.should_stop = False
        app.stopped_event = Tevent()
        app.started_event = Tevent()
        app._thread = Thread(target=app.start, daemon=True)
        app._thread.start()
        ioConf.event_wait_clear(app.started_event)

    def __getattr__(app, name):
        if name in app.colors:
            async def dynamic_method(*args, **kwargs):
                return await app.__log__(app.colors.__getattr__(name), *args, **kwargs)

            setattr(app, name, dynamic_method)
            return dynamic_method

        raise AttributeError("'DefaultLogger' object has no attribute '%s'" % name)

    def __log_actual__(app, color = "", log: str = "", add_new_line: bool = True, raw: bool = None):
        if raw is None:
            if not isinstance(log, str):
                log = str(log)
    
            if add_new_line and not "\n" in log: log += "\n"
    
            if not log.startswith("\\"):
                prec = "\r"
            else:
                prec = ""

            sys_stdout.write("%s%s%s" % (prec, color, log))
        else:
            sys_stdout.write(raw)

        sys_stdout.flush()

    def dead(app):
        return app.should_stop

    async def __log__(app, *args, **kwargs):
        event = SharpEvent(False)
        await wrap_future(run_coroutine_threadsafe(app.logs.put((args, kwargs, event)), app.loop))
        await event.wait()

    async def raw(app, log, *args, **kwargs):
        return await app.__log__(*args, raw = log, **kwargs)

    async def loop_setup(app):
        app.logs = Enqueue(maxsize=app.maxsize)
        app.log_idle_event = SharpEvent()
        app.log_idle_event.set()

    async def log_worker(app):
        await app.loop_setup()
        app.started_event.set()

        while not app.dead():
            await app.logs.get_one(pop=False)
            while app.logs.queue:
                args, kwargs, event = app.logs.popleft()
                app.__log_actual__(*args, **kwargs)
                event.loop.call_soon(event.set)

            if not app.logs.queue:
                app.log_idle_event.set()
            else:
                app.log_idle_event.clear()

    async def flush(app):
        if app.logs.queue: return await wrap_future(run_coroutine_threadsafe(app.log_idle_event.wait(), app.loop))

    def start(app):
        app.loop = new_event_loop()
        try:
            app.loop.run_until_complete(app.log_worker())
        finally:
            app.stopped_event.set()

    def stop(app):
        app.should_stop = True
        app.logs.loop.call_soon_threadsafe(app.logs.wakeup)
        app.stopped_event.wait()
        app._thread.join()
        sys_stdout.flush()

def configure_uvloop_loop():
    from uvloop import EventLoopPolicy as uvloop_EventLoopPolicy
    set_event_loop_policy(uvloop_EventLoopPolicy())
    ioConf.get_event_loop()

def configure_asyncio_loop():
    ioConf.get_event_loop()

routines = {
    ("configure_uvloop_loop()", "configure_asyncio_loop()"),
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

class __log__:
    known_exceptions = ()

    def __init__(app): pass

    def __getattr__(app, name):
        if name in logger.colors:
            async def dynamic_method(*args, **kwargs):
                return await app.__log__(*args, **kwargs, logger_=logger.__getattr__(name))

            setattr(app, name, dynamic_method)
            return dynamic_method

        raise AttributeError("'DefaultLogger' object has no attribute '%s'" % name)

    async def __log__(app, r: Any = None, message: Any = None, color: (None, str) = None, logger_: Any = None, frame = 3, func = None, **kwargs):
        if hasattr(r, "transport"):
            message = str(message).strip()
            if message in app.known_exceptions: return
            await logger_("%s @ %s • %s | [%s:%s] %s" % (ioConf.get_func_name(frame) if func is None else "<%s>" % func.__qualname__ if hasattr(func, "__qualname__") else func.__name__, r.identifier, str(dt.now()), r.ip_host, str(r.ip_port), message))
        else:
            _ = str(r).strip()
            if message:
                _ += message

            message = _
            msg = message

            if msg == "":
                return await logger_(message, **kwargs)

            await logger_("%s • %s | %s" % (ioConf.get_func_name(frame) if func is None else "<%s>" % func.__qualname__ if hasattr(func, "__qualname__") else func.__name__, str(dt.now()), message))

logger = Default_logger(name='BlazeioLogger')

Log = __log__()

routine_executor({
    ('p = Log.info', 'p = None'),
    ('log = logger', 'p = None')
})

class __ReMonitor__:
    __slots__ = ("Monitoring_thread", "event_loop", "event_loops", "Monitoring_thread_loop", "_start_monitoring", "servers", "main", "stopped_event", "terminated_event", "started_event", "tasks")
    default_payload_timeout = float(60*60)
    def __init__(app):
        ioConf.add_shutdown_callback(app.Monitoring_thread_join)
        app.tasks = []
        app.event_loop = loop
        app.event_loops = [app.event_loop]
        app.servers = []
        app.main = None
        app._start_monitoring = SharpEvent(evloop = app.event_loop)
        app.started_event = Tevent()
        app.stopped_event = Tevent()
        app.terminated_event = Tevent()
        app.Monitoring_thread = Thread(target=app.Monitoring_thread_monitor, args=(app,), daemon = True)
        app.Monitoring_thread.start()
        ioConf.event_wait_clear(app.started_event)

    def reboot(app):
        app.Monitoring_thread_join()
        app.__init__()

    def add_server(app, server):
        if server.loop not in app.event_loops:
            app.event_loops.append(server.loop)
        server.on_exit_middleware(lambda: app.rm_server(server))
        app.servers.append(server)
        app._start_monitoring.set()

    def rm_server(app, server):
        if server in app.servers:
            if server.loop in app.event_loops: app.event_loops.remove(server.loop)
            app.servers.remove(server)

    def stop(app):
        if app.terminated_event.is_set(): return
        app.terminated_event.set()
        app.stopped_event.wait()

    def Monitoring_thread_join(app):
        app.stop()
        app.Monitoring_thread.join()

    def Monitoring_thread_monitor(app, parent=None):
        app.Monitoring_thread_loop = new_event_loop()
        app.main = app.Monitoring_thread_loop.create_task(app.__monitor_loop__())
        app.tasks.append(app.main)
        app.Monitoring_thread_loop.run_until_complete(app.main)

    async def __monitor_loop__(app):
        try:
            app.started_event.set()
            await wrap_future(run_coroutine_threadsafe(app._start_monitoring.wait(), app._start_monitoring.loop))

            while not app.terminated_event.is_set():
                for server in app.servers:
                    await wrap_future(run_coroutine_threadsafe(app.analyze_protocols(), app.event_loop))
                    app.terminated_event.wait(server.ServerConfig.__timeout_check_freq__)
        finally:
            app.stopped_event.set()

    async def enforce_health(app, Payload, task):
        if Payload.transport.is_closing():
            await app.cancel(Payload, task, "BlazeioHealth:: Task [%s] diconnected." % task.get_name())
            return True

    async def cancel(app, Payload, task, msg: (None, str) = None):
        try: task.cancel()
        except CancelledError: pass
        except KeyboardInterrupt: raise
        except Exception as e: await Log.warning("Blazeio", str(e))

        try:
            if msg: await Log.warning(Payload, msg)
        except:
            pass

    async def inspect_task(app, task):
        if hasattr(task, "__BlazeioProtocol__"):
            Payload = task.__BlazeioProtocol__
        elif hasattr(task, "__BlazeioClientProtocol__"):
            Payload = task.__BlazeioClientProtocol__
        else:
            return

        if not hasattr(Payload, "__perf_counter__"):
            Payload.__perf_counter__ = perf_counter()

        if await app.enforce_health(Payload, task): return

        if not Payload.__timeout__: return

        duration = float(perf_counter() - getattr(Payload, "__perf_counter__"))

        condition = duration >= Payload.__timeout__

        if condition: await app.cancel(Payload, task, "BlazeioTimeout:: Task [%s] cancelled due to Timeout exceeding the limit of (%s), task took (%s) seconds." % (task.get_name(), str(Payload.__timeout__), str(duration)))

    async def analyze_protocols(app):
        for event_loop in app.event_loops:
            for task in all_tasks(loop=event_loop):
                if task not in app.tasks:
                    try: await app.inspect_task(task)
                    except AttributeError: pass
                    except KeyboardInterrupt: raise
                    except Exception as e: print(e)

ReMonitor = __ReMonitor__()
