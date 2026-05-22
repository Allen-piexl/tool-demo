#!/usr/bin/env bash
set -e
export PYTHONPATH=$(pwd)
uvicorn amazon_primitive.server:app --host 0.0.0.0 --port ${AMAZON_PORT:-8003}
