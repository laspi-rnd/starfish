#!/bin/bash

# Check if MIDDLEWARE_CALLBACK_PORT is set
if [ -z "$MIDDLEWARE_CALLBACK_PORT" ]; then
  echo "Error: MIDDLEWARE_CALLBACK_PORT is not set. Please set it before running this script."
  exit 1
fi

# Run the Python worker
uv run python worker.py &

# Run the middleware callback API
uv run uvicorn middleware.callback_api:app --reload --host 0.0.0.0 --port $MIDDLEWARE_CALLBACK_PORT &

# Wait for both processes to finish
wait
