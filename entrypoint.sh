#!/usr/bin/env bash

set -e
set -u
set -o pipefail

: "${API_PORT:=8080}"
: "${GUNICORN_RELOAD:=false}"

reload_args=()
if [ "${GUNICORN_RELOAD}" = "true" ]; then
  reload_args+=(--reload)
fi

exec gunicorn api:app \
  --workers 2 \
  --max-requests 200 \
  --max-requests-jitter 50 \
  --timeout 50 \
  --access-logfile - \
  "${reload_args[@]}" \
  --bind 0.0.0.0:${API_PORT}

#  --log-level debug \
