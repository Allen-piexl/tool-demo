#!/usr/bin/env bash
set -e
export PYTHONPATH=$(pwd)
uvicorn stock_primitive.server:app --host 0.0.0.0 --port ${STOCK_PORT:-8001}
