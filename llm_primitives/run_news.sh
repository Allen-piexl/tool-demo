#!/usr/bin/env bash
set -e
export PYTHONPATH=$(pwd)
uvicorn news_primitive.server:app --host 0.0.0.0 --port ${NEWS_PORT:-8002}
