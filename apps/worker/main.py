import threading
import uvicorn
from rq import Worker, Queue, Connection

from app.services.queue import get_redis


def _start_health():
    uvicorn.run("health:app", host="0.0.0.0", port=8001, log_level="warning")


def main():
    t = threading.Thread(target=_start_health, daemon=True)
    t.start()
    with Connection(get_redis()):
        worker = Worker([Queue("default")])
        worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
