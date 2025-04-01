"""Test celery-healthcheck."""

import celery_healthcheck


def test_import() -> None:
    """Test that the  can be imported."""
    assert isinstance(celery_healthcheck.__name__, str)