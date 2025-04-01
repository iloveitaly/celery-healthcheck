from celery_healthcheck.server import HealthCheckServer


def register(celery_app):
    celery_app.steps["worker"].add(HealthCheckServer)
