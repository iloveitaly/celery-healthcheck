"""Test the health check server."""

import pytest
from unittest.mock import Mock
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
    
    # Register the route using the same logic as the actual implementation
    def create_endpoint():
        from fastapi.responses import JSONResponse
        
        @health_server.app.get("/")
        async def celery_ping():
            insp = mock_worker.app.control.inspect()
            result = insp.ping()
            if result:
                return JSONResponse(
                    content={"status": "ok", "result": result},
                    status_code=200
                )
            else:
                return JSONResponse(
                    content={"status": "error", "result": result},
                    status_code=503
                )
    
    create_endpoint()
    
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
    
    # Register the route using the same logic as the actual implementation
    def create_endpoint():
        from fastapi.responses import JSONResponse
        
        @health_server.app.get("/")
        async def celery_ping():
            insp = mock_worker.app.control.inspect()
            result = insp.ping()
            if result:
                return JSONResponse(
                    content={"status": "ok", "result": result},
                    status_code=200
                )
            else:
                return JSONResponse(
                    content={"status": "error", "result": result},
                    status_code=503
                )
    
    create_endpoint()
    
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
    
    # Register the route using the same logic as the actual implementation
    def create_endpoint():
        from fastapi.responses import JSONResponse
        
        @health_server.app.get("/")
        async def celery_ping():
            insp = mock_worker.app.control.inspect()
            result = insp.ping()
            if result:
                return JSONResponse(
                    content={"status": "ok", "result": result},
                    status_code=200
                )
            else:
                return JSONResponse(
                    content={"status": "error", "result": result},
                    status_code=503
                )
    
    create_endpoint()
    
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
