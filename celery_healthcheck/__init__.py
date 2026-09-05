from celery_healthcheck.beat import register_beat
from celery_healthcheck.server import HealthCheckServer


def register(celery_app):
    celery_app.steps["worker"].add(HealthCheckServer)
    register_beat(celery_app)
