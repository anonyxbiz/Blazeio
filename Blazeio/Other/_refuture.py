from ..Dependencies import CancelledError, get_event_loop, deque, InvalidStateError

_PENDING: str = "_PENDING"
_CANCELLED: str = "_CANCELLED"
_FINISHED: str = "_FINISHED"
_INFINITE: str = "_INFINITE"
_FINITE: str = "_FINITE"

class reFuture:
    __slots__ = ("_loop", "_sleepers", "_result", "_state", "_mortality", "_exception", "_asyncio_future_blocking", "_cancel_message")

    def __init__(app, loop = None, mortality = _INFINITE):
        app._sleepers, app._loop, app._result, app._state, app._mortality, app._exception, app._asyncio_future_blocking, app._cancel_message = deque(), loop or get_event_loop(), None, _PENDING, mortality, None, False, None

    def __repr__(app):
        return "<reFuture %s result=%s>" % (app._state.lower()[1:], str(app._result))

    def cancelled(app): return app._state == _CANCELLED

    def done(app): return app._state != _PENDING

    def is_infinite(app): return app._mortality != _FINITE

    def exception(app): return app._exception

    def set_exception(app, exception):
        if isinstance(exception, StopIteration):
            new_exc = RuntimeError("StopIteration interacts badly with generators and cannot be raised into a Future")
            new_exc.__cause__ = exception
            new_exc.__context__ = exception
            exception = new_exc

        app._exception = exception
        app._state = _FINISHED
        app._mortality = _FINITE
        return app.flush()

    def add_done_callback(app, fn, context=None):
        if app._state != _PENDING:
            app._loop.call_soon(fn, app, context=context)
        else:
            app._sleepers.append((fn, context))

    def result(app):
        if app._exception is not None:
            raise app.exception()

        if app._state != _FINISHED:
            if app._exception is None:
                app._exception = InvalidStateError("Result is not ready.")

        return app._result

    def set_result(app, result):
        if app._state == _CANCELLED:
            raise app.exception()

        elif app._state == _FINISHED:
            return

        app._state = _FINISHED
        app._result = result
        app.flush()

    def cancel(app, msg: str = "Future was cancelled."):
        if app._state != _PENDING: raise InvalidStateError(app._state)

        app._state = _CANCELLED
        app._mortality = _FINITE
        app._exception = CancelledError(msg)

        return app.flush()

    def awake(app):
        while app._sleepers:
            cb, ctx = app._sleepers.popleft()
            app._loop.call_soon(cb, app, context=ctx)

    def restart(app):
        if app._state == _PENDING: return app

        app._result, app._state, app._asyncio_future_blocking = None, _PENDING, False
        return app

    def flush(app):
        app.awake()

        if app.is_infinite(): app._loop.call_soon(app.restart)

    def __await__(app):
        if not app.done():
            app._asyncio_future_blocking = True
            yield app

        if not app.done():
            raise RuntimeError("await wasn't used with future")

        return app.result()

class reTask(reFuture):
    __slots__ = ("_coro", "__taskpool_timer_handle__", "__taskpool_callbacks__",)

    def __init__(app, coro, *a, **k):
        app._coro = coro

        super().__init__(*a, mortality = _FINITE, **k)

        app._loop.call_soon(app._step)

    def _step(app, exc=None):
        if app.done():
            exc = InvalidStateError("_step(): already done")
        try:
            app._step_run_and_handle_result(exc)
        finally:
            app = None

    def _step_run_and_handle_result(app, exc):
        try:
            if exc is None:
                result = app._coro.send(None)
            else:
                result = app._coro.throw(exc)
        except StopIteration as exc:
            if app.cancelled():
                app.cancel(exc.value)
            else:
                app.set_result(exc.value)

        except CancelledError as e:
            app.set_exception(e)
        except BaseException as e:
            app.set_exception(e)
        else:
            if result and result is not app:
                result.add_done_callback(app._wakeup)
            else:
                app.set_result(result)

    def _wakeup(app, fut):
        try:
            fut.result()
        except BaseException as e:
            app.set_exception(e)
        else:
            app._step()
        
        app = None

def tempFut(result):
    fut = reFuture(mortality = _FINITE)
    fut._loop.call_soon(fut.set_result, result)
    return fut
