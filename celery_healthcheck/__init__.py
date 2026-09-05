from celery_healthcheck.beat import register_beat
from celery_healthcheck.server import HealthCheckServer
from celery_healthcheck.version import __version__


def register(celery_app):
    celery_app.steps["worker"].add(HealthCheckServer)
    register_beat(celery_app)


__all__ = ["HealthCheckServer", "__version__", "register", "register_beat"]
