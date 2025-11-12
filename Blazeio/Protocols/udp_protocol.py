# ./udp_protocol.py
import Blazeio as io
from asyncio import DatagramProtocol, wait_for, TimeoutError

class sTransport:
    __slots__ = ("_is_closing", "transport", "prot", "srv")
    def __init__(app, transport, prot, srv):
        app.transport, app.prot, app.srv = transport, prot, srv
        app._is_closing = False

    def __getattr__(app, *args):
        return getattr(app.transport, *args)

    def is_closing(app):
        return app._is_closing

    def write(app, *args):
        return app.prot.sendto(*args)

    def get_extra_info(app, info: str):
        if info == "peername":
            return app.prot.addr
            
        return app.transport.get_extra_info(info)

    def close(app):
        return app.srv.close_prot(app.prot)

class BlazeioDatagram:
    __slots__ = ()
    bounds = io.ddict(
        close = b'\x01'
    )
    def cancel(app):
        ...

    def error_received(app, exc):
        ...

    def datagram_received(app, data, addr):
        size = len(data)
        app.get_buffer(size)[:size] = memoryview(data)
        return app.buffer_updated(size)

    def sendto(app, data):
        if not app.transport.is_closing():
            app.transport.sendto(data, app.addr)
        else:
            raise io.ClientDisconnected()

    async def writer(app, data):
        return app.sendto(data)

    async def push(app, data):
        return app.sendto(data)

class BlazeioUdpServerProtocolObject(io.BlazeioServerProtocol, io.BlazeioPayloadUtils, io.ExtraToolset, BlazeioDatagram):
    __slots__ = ("loop", "handler", "addr",)
    def __init__(app, handler = None, addr = None, transport = None, evloop = None):
        app.loop = evloop or io.get_event_loop()
        app.handler = handler
        app.addr = addr
        super().__init__(app.handler, app.loop, io.INBOUND_CHUNK_SIZE)

class BlazeioUdpServerProtocol(BlazeioDatagram, DatagramProtocol):
    __slots__ = ("loop", "handler", "addr", "transport", "protocol", "wait_closed", "protocols")
    def __init__(app, handler = None, evloop = None):
        app.loop = evloop or io.get_event_loop()
        app.handler = handler
        app.protocols = {}
        app.wait_closed = io.SharpEvent()

    def close_prot(app, prot):
        prot.transport._is_closing = True
        prot.connection_lost(prot.addr)
        app.protocols.pop(prot.addr, None)
        try:
            prot.sendto(app.bounds.close)
        except io.ClientDisconnected:
            ...

    def forwarder(app, method, *args, **kwargs):
        for addr in app.protocols:
            if (prot := app.protocols.get(addr)):
                getattr(prot, method)(*args, **kwargs)

    def cancel(app):
        app.forwarder("cancel")

    def error_received(app, exc):
        app.forwarder("error_received", exc)

    def datagram_received(app, data, addr):
        if not (prot := app.protocols.get(addr)):
            app.protocols[addr] = (prot := BlazeioUdpServerProtocolObject(app.handler, addr, None, app.loop))
            prot.connection_made(sTransport(app.transport, prot, app))

        if data == app.bounds.close:
            app.close_prot(prot)
        else:
            prot.datagram_received(data, addr)

    def connection_made(app, transport):
        app.transport = transport

    def connection_lost(app, exc):
        app.forwarder("connection_lost", exc)

class BlazeioUdpServer:
    __slots__ = ("transport", "protocol", "handler", "host", "port", "args", "kwargs", "context_protocol")
    def __init__(app, handler, host, port, context_protocol, *args, **kwargs):
        app.handler = handler
        app.host = host
        app.port = port
        app.args = args
        app.context_protocol = context_protocol
        app.kwargs = kwargs

    def close(app):
        app.transport.close()

    def cancel(app):
        ...
    
    def __await__(app):
        yield None
        return app

    async def __aenter__(app):
        app.transport, app.protocol = await io.ioConf.loop.create_datagram_endpoint(lambda: app.context_protocol(app.handler), local_addr=(app.host, app.port))
        return app

    async def __aexit__(app, ext_type = None, ext_value = None, tb = None):
        app.close()
        return False

    async def start_serving(app):
        ...

    async def serve_forever(app):
        await app.protocol.wait_closed.wait()

class BlazeioUdpClientProtocol(io.BlazeioProtocol, BlazeioDatagram, DatagramProtocol):
    __slots__ = ("loop", "handler", "addr", "transport", "protocol", "wait_closed", "__buff__", "__stream__", "__buff__memory__", "cancel_on_disconnect", "__is_buffer_over_high_watermark__", "__evt__", "__overflow_evt__")
    def __init__(app, evloop = None):
        app.loop = evloop or io.get_event_loop()
        app.__buff__ = bytearray(io.INBOUND_CHUNK_SIZE)
        app.__stream__ = io.deque()
        app.__buff__memory__ = memoryview(app.__buff__)
        app.cancel_on_disconnect = False
        app.__is_buffer_over_high_watermark__ = False
        app.__evt__ = io.SharpEvent()
        app.__overflow_evt__ = io.SharpEvent()
        app.wait_closed = io.SharpEvent()

    def connection_made(app, transport):
        app.transport = transport
        app.addr = app.transport.get_extra_info("peername")

    def close(app):
        app.transport.close()

class BlazeioUdpClient(BlazeioUdpClientProtocol):
    __slots__ = ("host", "port", "args", "kwargs",)
    def __init__(app, host: str, port: int, *args, loop: any = None, **kwargs):
        super().__init__(loop)
        app.host, app.port, app.args, app.kwargs = host, port, args, kwargs
    
    def datagram_received(app, data, addr):
        if data == app.bounds.close:
            app.transport.close()

        super().datagram_received(data, addr)

    async def __aenter__(app):
        await app.create_connection()
        return app

    async def __aexit__(app, *args):
        await app.writer(app.bounds.close)
        app.cancel()
        return False

    async def create_connection(app):
        host, port = app.host, app.port

        transport, protocol = await app.loop.create_datagram_endpoint(lambda: app, remote_addr=(app.host, app.port))

        return (transport, protocol)

udp_protocol = io.ddict(BlazeioUdpServerProtocol = BlazeioUdpServerProtocol, BlazeioUdpServer = BlazeioUdpServer, BlazeioUdpClient = BlazeioUdpClient)

if __name__ == "__main__":
    ...