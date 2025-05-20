from concurrent.futures import ProcessPoolExecutor
from multiprocessing import Process

class ProcessPoolDaemonizer(ProcessPoolExecutor):
    def __init__(app, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _adjust_process_count(app):
        for _ in range(len(app._processes), app._max_workers):
            (proc := Process(target=app._queue_management_worker, daemon=True)).start()
            app._processes[proc.pid] = proc

if __name__ == "__main__":
    pass