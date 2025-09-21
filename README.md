# Celery Healthcheck

A lightweight HTTP health check server for Celery workers, designed to work with cloud platforms like Azure that only support TCP-based health probes.

## Problem

When deploying Celery workers to cloud platforms like Azure, you need a way to verify the worker's health. However, Azure doesn't allow command execution for health checks and only supports TCP-based probes. This makes it challenging to properly monitor Celery workers.

## Solution

`celery-healthcheck` spins up a small FastAPI server within each Celery worker that exposes an HTTP endpoint to check the worker's health status. This allows cloud platforms to perform health checks via HTTP requests rather than command execution.

Importantly, the ping-based healthcheck reports whether the worker is connected to the broker and responsive. However, it does not guarantee that the worker is processing tasks successfully nor does it indicate a problem with the Celery worker itself, as the ping can fail for reasons like the broker being unavailable. It is not recommended to autoheal the Celery worker based on the healthcheck due to the noise inherent in this signal.

## Installation

```bash
pip install celery-healthcheck
```

## Usage

Add the health check server to your Celery application:

```python
from celery import Celery
import celery_healthcheck

app = Celery('myapp')
app.config_from_object('myapp.celeryconfig')

# Register the health check server
celery_healthcheck.register(app)
```

Now start your worker as usual

```sh
celery -A myapp worker -l info
```

## How It Works

The health check server:

1. Embeds a FastAPI application inside your Celery worker
2. Runs on port 9000 by default (configurable)
3. Exposes an HTTP endpoint (`GET /`) that:
   - Uses Celery's inspect API to ping the current worker only
   - Returns a JSON response with status and result

## API Endpoints

### GET /

Pings the Celery worker and returns its status.

**Response:**

```json
{
  "status": "ok",  // or "error" if worker doesn't respond
  "result": { ... } // Raw response from Celery's ping command
}
```

## Configuration

The health check app can be configured via the main celery app it is registered on.

- `healthcheck_port`: The port on which the health check server will listen (default: 9000)
- `healthcheck_ping_timeout`: The timeout for the ping command to the worker (default: 2.0 seconds)

## Azure Configuration

When configuring Azure health probes:

1. Set the probe to use HTTP
2. Point to port 9000
3. Use the path "/"
4. A 200 OK response indicates the worker is healthy

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development tasks

Run tests

```sh
uv run pytest
```

Format

```sh
uvx ruff format
```
