#!/usr/bin/env bash

#set -e
#set -u
#set -o pipefail
#python api.py

set -e
set -u
set -o pipefail

: "${API_PORT:=8080}"

exec gunicorn \
  --workers 2 \
  --threads 4 \
  --bind 0.0.0.0:${API_PORT} \
  api:app