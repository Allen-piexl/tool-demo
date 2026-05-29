#!/usr/bin/env bash
set -e

export PYTHONPATH=$(pwd)

uvicorn router_service.server:app --host 0.0.0.0 --port ${ROUTER_PORT:-8000} &
PID0=$!
(
  export PRIMITIVE_ID=stock
  uvicorn ondemand_gateway:app --host 0.0.0.0 --port ${STOCK_PORT:-8001}
) &
PID1=$!
(
  export PRIMITIVE_ID=news
  uvicorn ondemand_gateway:app --host 0.0.0.0 --port ${NEWS_PORT:-8002}
) &
PID2=$!
(
  export PRIMITIVE_ID=amazon
  uvicorn ondemand_gateway:app --host 0.0.0.0 --port ${AMAZON_PORT:-8003}
) &
PID3=$!
(
  export PRIMITIVE_ID=kiwi
  uvicorn ondemand_gateway:app --host 0.0.0.0 --port ${KIWI_PORT:-8010}
) &
PID4=$!

echo "PrimitiveRouterService running on http://localhost:${ROUTER_PORT:-8000}"
echo "StockPrimitiveModel gateway running on http://localhost:${STOCK_PORT:-8001}"
echo "NewsPrimitiveModel gateway running on http://localhost:${NEWS_PORT:-8002}"
echo "AmazonPrimitiveModel gateway running on http://localhost:${AMAZON_PORT:-8003}"
echo "KiwiBookingPrimitiveModel gateway running on http://localhost:${KIWI_PORT:-8010}"
echo "Press Ctrl+C to stop."

trap "kill $PID0 $PID1 $PID2 $PID3 $PID4" EXIT
wait
