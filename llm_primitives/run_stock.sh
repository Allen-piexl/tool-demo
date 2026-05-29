#!/usr/bin/env bash
set -e
export PYTHONPATH=$(pwd)
export PRIMITIVE_ID=stock
uvicorn ondemand_gateway:app --host 0.0.0.0 --port ${STOCK_PORT:-8001}
