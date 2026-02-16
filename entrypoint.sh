#!/usr/bin/env bash

set -e
set -u
set -o pipefail

: "${API_PORT:=8080}"

exec gunicorn api:app \
  --workers 2 \
  --max-requests 200 \
  --max-requests-jitter 50 \
  --timeout 50 \
  --access-logfile - \
  --bind 0.0.0.0:${API_PORT}

#  --log-level debug \
