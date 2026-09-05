"""Test the beat health check."""

import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from celery_healthcheck import beat


@pytest.fixture(autouse=True)
def reset_beat_state():
    """Reset module-level tick state so tests don't leak into each other."""
    with beat._lock:
        beat._last_tick_time = None
        beat._max_tick_age = None
    yield
    with beat._lock:
        beat._last_tick_time = None
        beat._max_tick_age = None


@pytest.fixture
def test_client():
    """TestClient for the module-level beat FastAPI app."""
    return TestClient(beat.app)


class FakeScheduler:
    """A bare stand-in for a real Celery scheduler instance.

    Deliberately not a Mock: Mock auto-creates attributes on access, which
    would make `getattr(scheduler, "_healthcheck_patched", False)` always
    truthy and defeat the double-patch guard under test.
    """

    def __init__(self, max_interval=300):
        self.max_interval = max_interval

    def tick(self, *args, **kwargs):
        return "original-return-value"


@pytest.fixture
def mock_scheduler():
    return FakeScheduler()


@pytest.fixture
def mock_celery_app():
    app = Mock()
    app.conf = object()  # getattr falls through to defaults, like test_server.py
    return app


def test_beat_ping_never_ticked(test_client):
    response = test_client.get("/")

    assert response.status_code == 503
    assert response.json()["status"] == "error"


def test_beat_ping_healthy(test_client):
    beat._touch_tick()
    beat._set_max_tick_age(60.0)

    response = test_client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["last_tick_age"] < 1.0
    assert body["max_tick_age"] == 60.0


def test_beat_ping_stale_tick(test_client):
    with beat._lock:
        beat._last_tick_time = time.time() - 100
    beat._set_max_tick_age(10.0)

    response = test_client.get("/")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "error"
    assert body["last_tick_age"] > 10.0


def test_patch_scheduler_tick_preserves_return_value_and_touches(mock_scheduler):
    assert beat._get_last_tick() is None

    result = mock_scheduler.tick()
    assert result == "original-return-value"

    beat._patch_scheduler_tick(mock_scheduler)

    result = mock_scheduler.tick()

    assert result == "original-return-value"
    assert beat._get_last_tick() is not None


def test_patch_scheduler_tick_does_not_double_wrap(mock_scheduler):
    call_count = {"n": 0}
    original_tick = mock_scheduler.tick

    def counting_tick(*args, **kwargs):
        call_count["n"] += 1
        return original_tick(*args, **kwargs)

    mock_scheduler.tick = counting_tick

    beat._patch_scheduler_tick(mock_scheduler)
    beat._patch_scheduler_tick(mock_scheduler)  # second call should be a no-op

    mock_scheduler.tick()

    assert call_count["n"] == 1


def test_resolve_max_tick_age_stock_default(mock_scheduler):
    conf = object()
    mock_scheduler.max_interval = 300

    assert beat._resolve_max_tick_age(conf, mock_scheduler) == 300 * 2.0 + 10.0


def test_resolve_max_tick_age_short_interval_scheduler(mock_scheduler):
    conf = object()
    mock_scheduler.max_interval = 5

    assert beat._resolve_max_tick_age(conf, mock_scheduler) == 5 * 2.0 + 10.0


def test_resolve_max_tick_age_explicit_override_wins(mock_scheduler):
    conf = SimpleNamespace(healthcheck_beat_max_tick_age=42.0)
    mock_scheduler.max_interval = 5

    assert beat._resolve_max_tick_age(conf, mock_scheduler) == 42.0


def test_resolve_max_tick_age_custom_multiplier(mock_scheduler):
    conf = SimpleNamespace(healthcheck_beat_tick_age_multiplier=3.0)
    mock_scheduler.max_interval = 10

    assert beat._resolve_max_tick_age(conf, mock_scheduler) == 10 * 3.0 + 10.0


def test_beat_init_handler_starts_server(mock_celery_app, mock_scheduler):
    handler = beat._make_beat_init_handler(mock_celery_app)
    sender = SimpleNamespace(scheduler=mock_scheduler)

    with patch("celery_healthcheck.beat.uvicorn.run") as mock_run:
        handler(sender=sender)

    mock_run.assert_called_once()
    assert mock_scheduler._healthcheck_patched is True
    assert beat._get_max_tick_age() is not None


def test_beat_init_handler_missing_scheduler_does_not_start_server(mock_celery_app):
    handler = beat._make_beat_init_handler(mock_celery_app)
    sender = SimpleNamespace()  # no `scheduler` attribute

    with patch("celery_healthcheck.beat.uvicorn.run") as mock_run:
        handler(sender=sender)

    mock_run.assert_not_called()
    assert beat._get_max_tick_age() is None


def test_register_beat_connects_handler(mock_celery_app, mock_scheduler):
    handler = beat.register_beat(mock_celery_app)
    try:
        # celery's Signal.send() caches receivers per-sender and requires the
        # sender to be hashable, unlike SimpleNamespace used elsewhere here.
        sender = Mock()
        sender.scheduler = mock_scheduler

        with patch("celery_healthcheck.beat.uvicorn.run") as mock_run:
            beat.beat_init.send(sender=sender)

        mock_run.assert_called_once()
    finally:
        beat.beat_init.disconnect(handler)
