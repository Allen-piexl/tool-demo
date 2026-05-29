#!/usr/bin/env bash
set -e
export PYTHONPATH=$(pwd)
export PRIMITIVE_ID=kiwi
uvicorn ondemand_gateway:app --host 0.0.0.0 --port ${KIWI_PORT:-8010}
