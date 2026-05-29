#!/usr/bin/env bash
set -e
export PYTHONPATH=$(pwd)
export PRIMITIVE_ID=amazon
uvicorn ondemand_gateway:app --host 0.0.0.0 --port ${AMAZON_PORT:-8003}
