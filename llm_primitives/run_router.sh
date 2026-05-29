#!/usr/bin/env bash
set -e
export PYTHONPATH=$(pwd)
uvicorn router_service.server:app --host 0.0.0.0 --port ${ROUTER_PORT:-8000}
