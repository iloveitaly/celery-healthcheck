"""Test the register function in celery-healthcheck."""

from unittest.mock import Mock, patch

from celery_healthcheck.server import HealthCheckServer


def test_register_function():
    """Test the register function adds HealthCheckServer to celery app steps and wires up beat."""
    from celery_healthcheck import register

    # Mock celery app
    mock_celery_app = Mock()
    mock_celery_app.steps = {"worker": Mock()}
    mock_celery_app.steps["worker"].add = Mock()

    # Call register function
    handler = None
    with patch("celery_healthcheck.beat.beat_init.connect") as mock_connect:
        register(mock_celery_app)
        handler = mock_connect.call_args[0][0]

    # Assert HealthCheckServer was added to worker steps
    mock_celery_app.steps["worker"].add.assert_called_once_with(HealthCheckServer)

    # Assert a beat_init handler was connected (works for any scheduler, no
    # subclassing or --scheduler flag required)
    assert callable(handler)
