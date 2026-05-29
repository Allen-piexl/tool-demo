#!/usr/bin/env bash
set -e
export PYTHONPATH=$(pwd)
export PRIMITIVE_ID=news
uvicorn ondemand_gateway:app --host 0.0.0.0 --port ${NEWS_PORT:-8002}
