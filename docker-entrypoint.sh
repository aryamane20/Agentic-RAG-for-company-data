#!/bin/sh
set -e

python3 docker_bootstrap.py

# exec (not a plain call) so uvicorn replaces this shell as PID 1 --
# otherwise it'd be a child process and wouldn't receive SIGTERM directly,
# breaking the graceful-shutdown Langfuse flush in backend/main.py's
# lifespan handler.
exec uvicorn backend.main:app --host 0.0.0.0 --port 8000
