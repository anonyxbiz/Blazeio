# Blazeio.Other.dom.py
import Blazeio as io

class Element:
    __slots__ = ("r", "element", "textContent", "on_enter", "on_exit", "attributes")
    non_closing_elements = ( b'meta', b'link', b'img', b'video', b'audio', b'br', b'hr', b'input', b'area', b'base', b'col', b'embed', b'source', b'track', b'wbr', b'param', b'keygen', b'command')
    def __init__(app, r: io.BlazeioProtocol, element: bytes, textContent: (None, bytes, str, io.AsyncIterable) = None, on_enter: (None, tuple) = None, on_exit: (None, tuple) = None, className: (None, str) = None, **attributes):
        app.r, app.element, app.textContent, app.on_enter, app.on_exit, app.attributes = r, element, textContent, on_enter, on_exit, attributes
        if className:
            app.attributes["class"] = className

    def __getattr__(app, key):
        def element(*args, **kwargs):
            return Element(app.r, key.encode(), *args, **kwargs)

        element.__name__ = key
        return element

    def __await__(app):
        yield from app.__aenter__().__await__()
        yield from app.__aexit__().__await__()
        return app
    
    def write(app, data: (str, bytes)):
        if not isinstance(data, bytes):
            data = data.encode()
        return app.r.write(data)

    async def __aenter__(app):
        await app.write(b'\n<%b%b>' % (app.element, (' %s' % ' '.join(['%s="%s"' % (key, value) for key, value in app.attributes.items()])).encode() if app.attributes else b''))

        if app.on_enter:
            for cb in app.on_enter:
                await cb(app)

        if app.textContent:
            if isinstance(app.textContent, str):
                await app.write(app.textContent.encode())

            elif isinstance(app.textContent, bytes):
                await app.write(app.textContent)

            elif isinstance(app.textContent, io.AsyncIterable):
                async for chunk in app.textContent:
                    await app.write(chunk)

        return app

    async def __aexit__(app, *args):
        if app.on_exit:
            for cb in app.on_exit:
                await cb(app)

        if app.element not in app.non_closing_elements:
            await app.write(b'</%b>\n' % app.element)

        return False

class Dom:
    __slots__ = ("r", "lang", "on_enter", "on_exit")
    def __init__(app, r: io.BlazeioProtocol, lang: str = "en", on_enter: (None, tuple) = None, on_exit: (None, tuple) = None):
        app.r, app.lang, app.on_enter, app.on_exit = r, lang.encode(), on_enter, on_exit

    async def __aenter__(app):
        await app.r.write(b'<!DOCTYPE html>\n<html lang="%b">' % app.lang)
        if app.on_enter:
            for cb in app.on_enter:
                await cb(app)

        return app

    async def __aexit__(app, *args):
        if app.on_exit:
            for cb in app.on_exit:
                await cb(app)

        await app.r.write(b'\n</html>')
        return False

    def __getattr__(app, key):
        def element(*args, **kwargs):
            return Element(app.r, key.encode(), *args, **kwargs)

        element.__name__ = key
        return element

if __name__ == "__main__":
    ...