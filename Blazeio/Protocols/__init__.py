# Blazeio.Protocols
__all__ = ('BlazeioProtocol',)

class BlazeioProtocol:
    __slots__ = ()
    def buffer_updated(app, nbytes):
        app.transport.pause_reading()
        app.__stream__.append(bytes(app.__buff__memory__[:nbytes]))
        app.__evt__.set()

    def get_buffer(app, sizehint):
        if sizehint > len(app.__buff__memory__):
            app.__buff__ = bytearray(sizehint)
            app.__buff__memory__ = memoryview(app.__buff__)
        elif sizehint <= 0:
            sizehint = len(app.__buff__memory__)

        return app.__buff__memory__[:sizehint]

    def connection_lost(app, exc):
        app.__evt__.set()
        app.__overflow_evt__.set()
        if app.cancel and app.cancel_on_disconnect: app.cancel()

    def eof_received(app):
        app.__is_at_eof__ = True
        app.__evt__.set()

    def pause_writing(app):
        app.__is_buffer_over_high_watermark__ = True

    def resume_writing(app):
        app.__is_buffer_over_high_watermark__ = False
        app.__overflow_evt__.set()

    def prepend(app, data):
        if app.transport.is_reading(): app.transport.pause_reading()
        app.__stream__.appendleft(data)
        app.__evt__.set()

    async def buffer_overflow_manager(app):
        if not app.__is_buffer_over_high_watermark__: return
        await app.__overflow_evt__.wait_clear()

    async def ensure_reading(app):
        if not app.transport.is_closing():
            if not app.__stream__ and not app.transport.is_reading():
                app.transport.resume_reading()

            await app.__evt__.wait_clear()

    def __initialize__(app):
        ...

    def __await__(app):
        yield from app.ensure_reading().__await__()
        return app.__stream__.popleft() if app.__stream__ else None

    async def __aiter__(app):
        while True:
            await app.ensure_reading()
            while app.__stream__:
                yield app.__stream__.popleft()
            else:
                if app.transport.is_closing() or app.__is_at_eof__: break