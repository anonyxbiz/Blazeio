# Blazeio.Modules.server_utilities
from ..Dependencies import *
from ..Dependencies.alts import *

class WildcardRouteMatcher:
    __slots__ = ("web", "delimiter", "max_del_count", "urp")
    """
        Implements O(1) wildcard route matching.
        Example:
            Matches path (/api/v2/dynamic_uuid, /api/v2/dynamic_uuid/dynamic_uuid, /api/v2/dynamic_uuid/dynamic_uuid/dynamic_uuid) to defined route route (/api/v2) or (/api/v2/)
        
        This does not affect Blazeio's O(1) routing as the .resolve method is only called when a direct route isnt defined, falling back to wildcard matching.
        
        `urp` is an acronym of `update_request_path`
    """
    def __init__(app, web, delimiter: str = "/", max_del_count: int = 20, urp: bool = 0):
        app.web, app.delimiter, app.max_del_count, app.urp = web, delimiter, max_del_count, urp

    def resolve(app, r):
        ref: str = r.path
        del_count: int = 0
        while (del_count := del_count + 1) <= app.max_del_count and (idx := ref.rfind(app.delimiter)) != -1 and (ref := ref[:idx]):
            if (route := app.web.declared_routes.get(ref) or app.web.declared_routes.get(ref + app.delimiter)):
                if app.urp:
                    r.path = route["route_name"]
                return route

if __name__ == "__main__": ...