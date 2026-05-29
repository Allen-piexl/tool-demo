#!/usr/bin/env bash
set -e

export PYTHONPATH=$(pwd)

uvicorn stock_primitive.server:app --host 0.0.0.0 --port ${STOCK_PORT:-8001} &
PID1=$!
uvicorn news_primitive.server:app --host 0.0.0.0 --port ${NEWS_PORT:-8002} &
PID2=$!
uvicorn amazon_primitive.server:app --host 0.0.0.0 --port ${AMAZON_PORT:-8003} &
PID3=$!
uvicorn kiwi_booking_primitive.server:app --host 0.0.0.0 --port ${KIWI_PORT:-8010} &
PID4=$!

echo "StockPrimitiveModel running directly on http://localhost:${STOCK_PORT:-8001}"
echo "NewsPrimitiveModel running directly on http://localhost:${NEWS_PORT:-8002}"
echo "AmazonPrimitiveModel running directly on http://localhost:${AMAZON_PORT:-8003}"
echo "KiwiBookingPrimitiveModel running directly on http://localhost:${KIWI_PORT:-8010}"
echo "Press Ctrl+C to stop."

trap "kill $PID1 $PID2 $PID3 $PID4" EXIT
wait
