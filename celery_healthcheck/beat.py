import logging
import threading
import time

import uvicorn
from celery.signals import beat_init
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

app = FastAPI()
logger = logging.getLogger("celery.ext.healthcheck.beat")

HEALTHCHECK_BEAT_DEFAULT_PORT = 9001
HEALTHCHECK_BEAT_DEFAULT_MAX_INTERVAL = 300.0
HEALTHCHECK_BEAT_DEFAULT_TICK_AGE_MULTIPLIER = 2.0
HEALTHCHECK_BEAT_TICK_AGE_GRACE = 10.0

_lock = threading.Lock()
_last_tick_time = None
_max_tick_age = None


def _touch_tick():
    global _last_tick_time
    with _lock:
        _last_tick_time = time.time()


def _get_last_tick():
    with _lock:
        return _last_tick_time


def _set_max_tick_age(value):
    global _max_tick_age
    with _lock:
        _max_tick_age = value


def _get_max_tick_age():
    with _lock:
        return _max_tick_age


def _resolve_max_tick_age(conf, scheduler):
    """Derive the staleness threshold from the scheduler's own max_interval.

    tick() legitimately sleeps up to max_interval between calls when nothing
    is due, so the threshold must be comfortably larger than that or a
    healthy beat process will fail the probe. max_interval varies widely by
    scheduler backend (e.g. stock Celery defaults to 300s, while
    django-celery-beat / redbeat are typically much shorter), so this is
    derived rather than hardcoded.
    """
    explicit = getattr(conf, "healthcheck_beat_max_tick_age", None)
    if explicit:
        return float(explicit)

    base = (
        getattr(scheduler, "max_interval", None)
        or HEALTHCHECK_BEAT_DEFAULT_MAX_INTERVAL
    )
    multiplier = float(
        getattr(
            conf,
            "healthcheck_beat_tick_age_multiplier",
            HEALTHCHECK_BEAT_DEFAULT_TICK_AGE_MULTIPLIER,
        )
    )
    return (base * multiplier) + HEALTHCHECK_BEAT_TICK_AGE_GRACE


@app.get("/")
async def beat_ping():
    last = _get_last_tick()
    max_tick_age = _get_max_tick_age() or HEALTHCHECK_BEAT_DEFAULT_MAX_INTERVAL

    if last is None:
        return JSONResponse(
            content={"status": "error", "detail": "beat has not ticked yet"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    age = time.time() - last

    if age > max_tick_age:
        return JSONResponse(
            content={
                "status": "error",
                "detail": f"last tick {age:.1f}s ago exceeds max_tick_age {max_tick_age:.1f}s",
                "last_tick_age": age,
                "max_tick_age": max_tick_age,
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return JSONResponse(
        content={"status": "ok", "last_tick_age": age, "max_tick_age": max_tick_age},
        status_code=status.HTTP_200_OK,
    )


def _patch_scheduler_tick(scheduler):
    """Wrap scheduler.tick() to record a heartbeat, without altering its return value.

    tick()'s return value is the sleep interval Celery's Service loop uses to
    schedule its next wakeup, so it must be passed through unchanged.
    """
    if getattr(scheduler, "_healthcheck_patched", False):
        return

    original_tick = scheduler.tick

    def tick(*args, **kwargs):
        _touch_tick()
        return original_tick(*args, **kwargs)

    scheduler.tick = tick
    scheduler._healthcheck_patched = True


def _start_server(port):
    def run_server():
        uvicorn.run(app, host="0.0.0.0", port=port)

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    logger.info(f"Beat health check server started on port {port}")


def _make_beat_init_handler(celery_app):
    def _on_beat_init(sender=None, **kwargs):
        scheduler = getattr(sender, "scheduler", None)
        if scheduler is None:
            logger.warning(
                "celery-healthcheck: could not find scheduler on beat_init sender, "
                "beat healthcheck will not be started"
            )
            return

        conf = celery_app.conf
        port = int(
            getattr(conf, "healthcheck_beat_port", HEALTHCHECK_BEAT_DEFAULT_PORT)
        )

        _patch_scheduler_tick(scheduler)
        _set_max_tick_age(_resolve_max_tick_age(conf, scheduler))
        _start_server(port)

    return _on_beat_init


def register_beat(celery_app):
    """Register a beat_init handler that installs a tick heartbeat and healthcheck server.

    This works with any scheduler (stock Celery, django-celery-beat, redbeat,
    or custom schedulers) since it patches the live scheduler instance that
    beat_init exposes, rather than requiring a scheduler subclass or a
    --scheduler CLI flag change.
    """
    handler = _make_beat_init_handler(celery_app)
    beat_init.connect(handler, weak=False)
    return handler
