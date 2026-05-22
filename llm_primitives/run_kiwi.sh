#!/usr/bin/env bash
set -e
export PYTHONPATH=$(pwd)
uvicorn kiwi_booking_primitive.server:app --host 0.0.0.0 --port ${KIWI_PORT:-8010}
