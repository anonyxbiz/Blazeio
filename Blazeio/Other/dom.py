# Blazeio.Other.dom.py
import Blazeio as io

class Element:
    __slots__ = ("r", "element", "on_enter", "on_exit", "attributes")
    non_closing_elements = ( b'meta', b'link', b'img', b'video', b'audio', b'br', b'hr', b'input', b'area', b'base', b'col', b'embed', b'source', b'track', b'wbr', b'param', b'keygen', b'command')
    known_attributes = ("textContent", "innerHTML")
    unsafe_attributes = ("href", "src")
    def __init__(app, r: io.BlazeioProtocol, element: bytes, on_enter: (None, tuple) = None, on_exit: (None, tuple) = None, className: (None, str) = None, **attributes):
        app.r, app.element, app.on_enter, app.on_exit, app.attributes = r, element, on_enter, on_exit, attributes
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
            if not isinstance(data, (str,)):
                data = str(data)
            data = data.encode()
        return app.r.write(data)

    async def __aenter__(app):
        await app.write(b'\n<%b%b>' % (app.element, ('%s%s' % (' ' if (attrs := ' '.join(['%s="%s"' % (key, value if key not in app.unsafe_attributes else io.escape(value.decode() if isinstance(value, (bytes,)) else str(value))) for key, value in app.attributes.items() if key not in app.known_attributes])) else '', attrs)).encode() if app.attributes else b''))

        if (innerHTML := app.attributes.get('innerHTML')):
            await app.write(innerHTML)

        if (textContent := app.attributes.get('textContent')):
            await app.write(io.escape(textContent.decode() if isinstance(textContent, (bytes,)) else str(textContent)))

        if app.on_enter:
            for cb in app.on_enter:
                await cb(app)

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