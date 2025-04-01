import threading

import uvicorn
from celery import bootsteps
from fastapi import FastAPI

app = FastAPI()


class HealthCheckServer(bootsteps.StartStopStep):
    def __init__(self, worker, **kwargs):
        self.worker = worker
        self.app = app
        self.thread = None

    def start(self, worker):
        @self.app.get("/")
        async def celery_ping():
            insp = worker.app.control.inspect()
            result = insp.ping()
            return {"status": "ok" if result else "error", "result": result}

        def run_server():
            uvicorn.run(self.app, host="0.0.0.0", port=9000)

        self.thread = threading.Thread(target=run_server, daemon=True)
        self.thread.start()

    def stop(self, worker):
        pass
