"""TicketPilot Worker - Processes tickets using multi-agent orchestration.

Supports multiple concurrent worker processes for parallel ticket processing.
The number of workers is controlled by the WORKER_CONCURRENCY environment variable.
"""
import redis
import json
import os
import time
import multiprocessing
import signal
from app.agents.orchestrator import Orchestrator

# Lazy Redis connection (one per process)
redis_client = None

WORKER_CONCURRENCY = int(os.getenv("WORKER_CONCURRENCY", "2"))


def _get_redis():
    """Get or create a Redis connection for the current process."""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"))
    return redis_client


def _process_loop(worker_id: int):
    """Worker process main loop.

    Each worker has its own Redis connection and Orchestrator instance.
    Blocks on brpop from the shared ticket_queue, processes one ticket at a time.
    """
    print(f"Worker {worker_id} started.")
    orchestrator = Orchestrator()

    while True:
        try:
            r = _get_redis()
            result = r.brpop("ticket_queue", timeout=5)
            if result:
                _, data = result
                ticket_data = json.loads(data)
                ticket_id = ticket_data.get("ticket_id")
                description = ticket_data.get("description")

                print(f"Worker {worker_id}: Processing ticket {ticket_id}...")
                resolution = orchestrator.process_ticket(ticket_id, description)
                print(f"Worker {worker_id}: Ticket {ticket_id} resolved")
        except Exception as e:
            print(f"Worker {worker_id} error: {e}")
            time.sleep(5)


def main():
    """Start the worker pool with the configured number of processes.

    Deprecated: Use async_worker.py for the event-driven pipeline.
    """
    import warnings
    warnings.warn(
        "sync worker.py is deprecated. Use async pipeline: python -m app.workers.async_worker",
        DeprecationWarning, stacklevel=2
    )
    print("WARNING: sync worker is deprecated. Use async worker instead.")
    print(f"Starting {WORKER_CONCURRENCY} worker processes...")
    processes = []

    for i in range(WORKER_CONCURRENCY):
        p = multiprocessing.Process(target=_process_loop, args=(i,))
        p.start()
        processes.append(p)

    def signal_handler(signum, frame):
        print("Shutting down workers...")
        for p in processes:
            p.terminate()
            p.join()
        print("All workers stopped.")

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    for p in processes:
        p.join()


if __name__ == "__main__":
    main()
