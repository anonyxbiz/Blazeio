# Blazeio.Utils.socket_ops
from ..Dependencies import *
from ..Dependencies.alts import *

from socket import SOL_SOCKET, IPPROTO_TCP, TCP_NODELAY, SO_KEEPALIVE, TCP_KEEPIDLE, TCP_KEEPINTVL, TCP_KEEPCNT

try:
    from socket import TCP_QUICKACK
except ImportError:
    TCP_QUICKACK = None

try:
    from socket import TCP_FASTOPEN
except ImportError:
    TCP_FASTOPEN = None

class TCPOptimizer:
    __slots__ = ("srv", "socket")
    def __init__(app, srv, KEEPIDLE: int = 30, KEEPINTVL: int = 10, KEEPCNT: int = 3):
        app.srv = srv
        app.socket = srv.sock()

        if TCP_QUICKACK:
            app.socket.setsockopt(IPPROTO_TCP, TCP_QUICKACK, 1)

        if TCP_FASTOPEN:
            app.socket.setsockopt(IPPROTO_TCP, TCP_FASTOPEN, 5)

        app.socket.setsockopt(IPPROTO_TCP, TCP_NODELAY, 1)
        app.socket.setsockopt(SOL_SOCKET, SO_KEEPALIVE, 1)
        app.socket.setsockopt(IPPROTO_TCP, TCP_KEEPIDLE, KEEPIDLE)
        app.socket.setsockopt(IPPROTO_TCP, TCP_KEEPINTVL, KEEPINTVL)
        app.socket.setsockopt(IPPROTO_TCP, TCP_KEEPCNT, KEEPCNT)

if __name__ == "__main__":
    ...