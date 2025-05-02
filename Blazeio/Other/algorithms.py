from ..Dependencies import *
from tracemalloc import start as tm_start, stop as tm_stop, take_snapshot

class Perf:
    @classmethod
    def ops_calc(app, amt: int = 10):
        conc = int(amt)
        def decor(func: Callable):
            nonlocal conc
            def wrapper(*args, **kwargs):
                nonlocal conc
                tm_start()

                sn1 = take_snapshot()
                start = perf_counter()

                while (conc := conc - 1):
                    func(*args, **kwargs)

                duration = perf_counter() - start

                stats = take_snapshot().compare_to(sn1, "lineno")
                tm_stop()

                filtered_stats = [str(i) for i in stats if all([x not in str(i) for x in ("python3.12", "importlib", "<")])]

                data = {
                    "function": func.__name__,
                    "duration_seconds": duration,
                    "memory_stats": filtered_stats,
                    "total_memory_used": "%s Kib" % str(sum(stat.size_diff for stat in stats) / 1024),
                    "total_allocations": sum(stat.count_diff for stat in stats)
                }

                get_event_loop().create_task(log.debug("<%s>: %s\n" % (func.__name__, dumps(data, indent=2, escape_forward_slashes=False))))
                return data
            
            wrapper()

            return func

        return decor
