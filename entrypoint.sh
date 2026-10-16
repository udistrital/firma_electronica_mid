#!/usr/bin/env bash

set -e
set -u
set -o pipefail

: "${API_PORT:=8080}"
: "${GUNICORN_RELOAD:=false}"
: "${GUNICORN_TIMEOUT:=300}"

reload_args=()
if [ "${GUNICORN_RELOAD}" = "true" ]; then
  reload_args+=(--reload)
fi

exec gunicorn api:app \
  --workers 2 \
  --max-requests 200 \
  --max-requests-jitter 50 \
  --timeout "${GUNICORN_TIMEOUT}" \
  --access-logfile - \
  "${reload_args[@]}" \
  --bind 0.0.0.0:${API_PORT}

#  --log-level debug \
