import Blazeio as io
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Process, current_process

class ProcessPoolDaemonizer(ProcessPoolExecutor):
    def __init__(app, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _adjust_process_count(app):
        for _ in range(len(app._processes), app._max_workers):
            (proc := Process(target=app._queue_management_worker, daemon=False)).start()
            app._processes[proc.pid] = proc

PoolScope = io.createScope("\x02")
PoolScope.args = ()
PoolScope.sync = io.ioCondition()

@PoolScope.add
def run_cmd():
    fn = PoolScope.fn
    args = PoolScope.args
    kwargs = io.ddict(PoolScope.kwargs)
    return fn(*args, **kwargs)

@PoolScope.add
async def ensure_non_blocking(fn, *args, **kwargs):
    async with PoolScope.sync:
        PoolScope.fn = fn
        PoolScope.args = args
        PoolScope.kwargs = kwargs
        with ProcessPoolDaemonizer() as pool:
            return await io.getLoop.run_in_executor(pool, PoolScope.run_cmd)

if __name__ == "__main__": ...