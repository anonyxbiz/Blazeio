from ..Dependencies import *

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

    def add_done_callback(app, fn, context=None):
        if app._state != _PENDING:
            app._loop.call_soon(fn, app, context=context)
        else:
            app._sleepers.append((fn, context))

    def result(app):
        if app._exception is not None:
            return app.exception()

        if app._state != _FINISHED:
            if app._exception is None:
                app._exception = InvalidStateError("Result is not ready.")

        return app._result

    def set_result(app, result):
        if app._state == _CANCELLED:
            raise app.exception()

        elif app._state != _PENDING:
            pass

        app._state = _FINISHED
        app._result = result
        app.flush()

    def cancel(app, msg: str = "Future was cancelled."):
        if app._state != _PENDING: raise InvalidStateError(app._state)

        app._state = _CANCELLED
        app._mortality = _FINITE
        app._exception = CancelledError(msg)

        app.flush()
        return True

    def awake(app):
        while app._sleepers:
            cb, ctx = app._sleepers.popleft()
            app._loop.call_soon(cb, app, context=ctx)

    def restart(app):
        if app._state == _PENDING: return app

        app._result, app._state, app._asyncio_future_blocking = None, _PENDING, False
        return app

    def flush(app):
        if not app._sleepers: return

        app.awake()

        if app.is_infinite(): app._loop.call_soon(app.restart)

    def __await__(app):
        if not app.done():
            app._asyncio_future_blocking = True
            yield app

        if not app.done():
            raise RuntimeError("await wasn't used with future")

        return app.result()
