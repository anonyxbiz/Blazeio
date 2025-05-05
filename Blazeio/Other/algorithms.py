from ..Dependencies import *
from tracemalloc import start as tm_start, stop as tm_stop, take_snapshot

class Perf:
    __slots__ = ("tasks",)
    def __init__(app):
        app.tasks = []

    def ops_calc(app, amt: int = 10, name: (None, str) = None):
        conc = int(amt)
        def decor(func: Callable):
            nonlocal conc
            def wrapper_sync(*args, **kwargs):
                nonlocal conc
                tm_start()
                sn1 = take_snapshot()
                start = perf_counter()

                while (conc := conc - 1):
                    func()

                duration = perf_counter() - start

                stats = take_snapshot().compare_to(sn1, "lineno")

                tm_stop()

                filtered_stats = [str(i) for i in stats if all([x not in str(i) for x in ("python3.12", "Blazeio/Other/algorithms.py", "importlib", "<")])]

                uniquestats = [i for i in stats if not "Blazeio/Other/algorithms.py" in str(i)]

                data = {
                    "function": name or func.__name__,
                    "duration_seconds": duration,
                    "memory_stats": filtered_stats,
                    "total_memory_used": "%s Kib" % str(sum(stat.size_diff for stat in uniquestats) / 1024),
                    "total_allocations": sum(stat.count_diff for stat in uniquestats)
                }

                get_event_loop().create_task(log.debug("<%s>: %s\n" % (name or func.__name__, dumps(data, indent=2, escape_forward_slashes=False))))
                return data

            async def wrapper_async(*args, **kwargs):
                nonlocal conc
                tm_start()

                sn1 = take_snapshot()
                start = perf_counter()

                while (conc := conc - 1):
                    await func(*args, **kwargs)

                duration = perf_counter() - start

                stats = take_snapshot().compare_to(sn1, "lineno")

                tm_stop()

                filtered_stats = [str(i) for i in stats if all([x not in str(i) for x in ("python3.12", "importlib", "<")])]

                data = {
                    "function": name or func.__name__,
                    "duration_seconds": duration,
                    "memory_stats": filtered_stats,
                    "total_memory_used": "%s Kib" % str(sum(stat.size_diff for stat in stats) / 1024),
                    "total_allocations": sum(stat.count_diff for stat in stats)
                }

                await log.debug("<%s>: %s\n\n" % (func.__name__, dumps(data, indent=2, escape_forward_slashes=False)))
                return data

            if "async" in func.__name__:
                app.tasks.append(loop.create_task(wrapper_async()))
            else:
                wrapper_sync()

            return func

        return decor
