"""Test the health check server."""

import pytest
from unittest.mock import Mock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient

from celery_healthcheck.server import HealthCheckServer


@pytest.fixture
def mock_worker():
    """Create a mock Celery worker."""
    worker = Mock()
    worker.app = Mock()
    worker.app.control = Mock()
    return worker


@pytest.fixture
def fresh_app():
    """Create a fresh FastAPI app for each test to avoid route conflicts."""
    return FastAPI()


@pytest.fixture
def health_server(mock_worker, fresh_app):
    """Create a HealthCheckServer instance with a fresh app."""
    server = HealthCheckServer(mock_worker)
    server.app = fresh_app  # Use fresh app instead of global one
    return server


@pytest.fixture
def test_client(fresh_app):
    """Create a test client for the fresh FastAPI app."""
    return TestClient(fresh_app)


def test_health_check_healthy_workers(health_server, mock_worker, test_client):
    """Test health check endpoint when workers are responding (healthy)."""
    # Mock the inspect ping to return worker responses
    mock_inspect = Mock()
    mock_inspect.ping.return_value = {
        "worker1@hostname": {"ok": "pong"},
        "worker2@hostname": {"ok": "pong"}
    }
    mock_worker.app.control.inspect.return_value = mock_inspect
    
    # Mock uvicorn.run to prevent actual server startup
    with patch('celery_healthcheck.server.uvicorn.run'):
        # Call the actual start method to register the route
        health_server.start(mock_worker)
    
    # Make request to health check endpoint
    response = test_client.get("/")
    
    # Assert healthy response
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["result"] == {
        "worker1@hostname": {"ok": "pong"},
        "worker2@hostname": {"ok": "pong"}
    }


def test_health_check_no_workers_responding(health_server, mock_worker, test_client):
    """Test health check endpoint when no workers are responding (unhealthy)."""
    # Mock the inspect ping to return None (no workers responding)
    mock_inspect = Mock()
    mock_inspect.ping.return_value = None
    mock_worker.app.control.inspect.return_value = mock_inspect
    
    # Mock uvicorn.run to prevent actual server startup
    with patch('celery_healthcheck.server.uvicorn.run'):
        # Call the actual start method to register the route
        health_server.start(mock_worker)
    
    # Make request to health check endpoint
    response = test_client.get("/")
    
    # Assert unhealthy response
    assert response.status_code == 503
    assert response.json()["status"] == "error"
    assert response.json()["result"] is None


def test_health_check_empty_worker_response(health_server, mock_worker, test_client):
    """Test health check endpoint when workers return empty response (unhealthy)."""
    # Mock the inspect ping to return empty dict (no workers responding)
    mock_inspect = Mock()
    mock_inspect.ping.return_value = {}
    mock_worker.app.control.inspect.return_value = mock_inspect
    
    # Mock uvicorn.run to prevent actual server startup
    with patch('celery_healthcheck.server.uvicorn.run'):
        # Call the actual start method to register the route
        health_server.start(mock_worker)
    
    # Make request to health check endpoint
    response = test_client.get("/")
    
    # Assert unhealthy response for empty result
    assert response.status_code == 503
    assert response.json()["status"] == "error"
    assert response.json()["result"] == {}


def test_health_server_initialization(mock_worker, fresh_app):
    """Test HealthCheckServer initialization."""
    server = HealthCheckServer(mock_worker)
    
    assert server.worker == mock_worker
    assert server.app is not None  # App should be set (either global or fresh)
    assert server.thread is None


def test_health_server_stop_method(health_server, mock_worker):
    """Test that stop method exists and can be called."""
    # Should not raise any exceptions
    health_server.stop(mock_worker)


def test_register_function():
    """Test the register function adds HealthCheckServer to celery app steps."""
    from celery_healthcheck import register
    
    # Mock celery app
    mock_celery_app = Mock()
    mock_celery_app.steps = {"worker": Mock()}
    mock_celery_app.steps["worker"].add = Mock()
    
    # Call register function
    register(mock_celery_app)
    
    # Assert HealthCheckServer was added to worker steps
    mock_celery_app.steps["worker"].add.assert_called_once_with(HealthCheckServer)
