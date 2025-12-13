# Blazeio.Other.cloudflare_d1
import Blazeio as io

class Client:
    __slots__ = ("url", "headers",)
    def __init__(app, url: str, headers: dict):
        app.url, app.headers = url, headers

    def escape(app, value):
        if value is None:
            return "NULL"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, bool):
            return "1" if value else "0"
        else:
            escaped = str(value).replace("'", "''")
            return "'%s'" % escaped

    async def sql(app, path: str, cmd: str, *args, result_only: bool = True):
        if args:
            count = 0
            index = 0
            while (idx := cmd[index:].find("?")) != -1:
                idx += index
                escaped = app.escape(args[count])
                cmd = cmd[:idx] + escaped + cmd[idx+1:]
                count += 1
                index = (idx + len(escaped))

        async with io.getSession.post(app.url + path, app.headers, json = io.ddict(sql = cmd)) as resp:
            data = await resp.json()
            if (result := data.get("result")) and (results := result[0].get("results")):
                return results if len(results) > 1 else io.ddict(results[0])

            if not result_only:
                return result

if __name__ == "__main__":
    ...