"""Test celery-healthcheck."""

import celery_healthcheck


def test_import() -> None:
    """Test that the package can be imported."""
    assert isinstance(celery_healthcheck.__name__, str)


def test_version() -> None:
    """Test that version is defined and is a string."""
    assert hasattr(celery_healthcheck, "__version__")
    assert isinstance(celery_healthcheck.__version__, str)
