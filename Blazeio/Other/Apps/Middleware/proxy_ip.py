# ./Other/Apps/Middleware/proxy_ip.py
import Blazeio as io

class IP:
    __slots__ = ("ip_headers")
    routes: io.Routemanager = io.Routemanager()
    def __init__(app, ip_headers: tuple = ("Ip_host", "True-client-ip")):
        io.set_from_args(app, locals(), (bool, str, int, float, tuple, list, dict))

    def __call__(app, *args, **kwargs):
        return app.routes(*args, **kwargs)

    async def before_middleware(app, r: io.BlazeioProtocol):
        if r.store is None:
            r.store = io.ddict()

        if (ip_host := r.headers.get(app.ip_headers[0]) or r.headers.get(app.ip_headers[1])):
            r.ip_host = ip_host

if __name__ == "__main__": ...