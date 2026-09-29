#!/bin/sh
set -e

python3 docker_bootstrap.py

# exec (not a plain call) so uvicorn replaces this shell as PID 1 --
# otherwise it'd be a child process and wouldn't receive SIGTERM directly,
# breaking the graceful-shutdown Langfuse flush in backend/main.py's
# lifespan handler.
#
# ${PORT:-8000}: Railway assigns a port at runtime via $PORT and expects
# the app to listen on it; local docker-compose never sets $PORT, so this
# falls back to the same 8000 as before.
exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"
