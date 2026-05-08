#!/usr/bin/env bash

set -e
set -u
set -o pipefail

: "${FIRMA_ELECTRONICA_MID_API_PORT:=${API_PORT:-8080}}"
: "${FIRMA_ELECTRONICA_MID_GUNICORN_RELOAD:=${GUNICORN_RELOAD:-false}}"

reload_args=()
if [ "${FIRMA_ELECTRONICA_MID_GUNICORN_RELOAD}" = "true" ]; then
  reload_args+=(--reload)
fi

exec gunicorn api:app \
  --workers 2 \
  --max-requests 200 \
  --max-requests-jitter 50 \
  --timeout 50 \
  --access-logfile - \
  "${reload_args[@]}" \
  --bind 0.0.0.0:${FIRMA_ELECTRONICA_MID_API_PORT}

#  --log-level debug \
