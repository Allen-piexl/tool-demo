# LLM Tool Primitives without Router

This demo hosts each Tool Primitive as an independent model-backed service.
There is no central router. The client directly calls the desired primitive endpoint.

Each primitive uses Qwen3:8B to understand the user query, extract API arguments, call the external API, and return a structured result.

## Services

| Primitive | Port | Endpoint | Example |
|---|---:|---|---|
| StockPrimitiveModel | 8001 | POST `/invoke` | `What is AAPL stock price?` |
| NewsPrimitiveModel | 8002 | POST `/invoke` | `latest news about climate change` |
| AmazonPrimitiveModel | 8003 | POST `/invoke` | `Search Amazon wireless earbuds` |
| KiwiBookingPrimitiveModel | 8010 | POST `/invoke`, `/sessions/*` | `Find a one-way flight from SEA to JFK on 2026-06-12` |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
ollama pull qwen3:8b
playwright install chromium
```

Start Ollama in another terminal if it is not already running:

```bash
ollama serve
```

Run all primitive services:

```bash
./run_all.sh
```

## Test

```bash
curl -X POST http://localhost:8001/invoke \
  -H "Content-Type: application/json" \
  -d '{"query":"What is AAPL stock price?"}'

curl -X POST http://localhost:8002/invoke \
  -H "Content-Type: application/json" \
  -d '{"query":"latest news about climate change"}'

curl -X POST http://localhost:8003/invoke \
  -H "Content-Type: application/json" \
  -d '{"query":"Search Amazon wireless earbuds"}'

curl -X POST http://localhost:8010/invoke \
  -H "Content-Type: application/json" \
  -d '{"query":"Find a one-way flight from SEA to JFK on 2026-06-12 for 1 adult"}'
```

## Architecture

```text
Client
  ├── POST /stock_primitive/invoke   -> StockPrimitiveModel(Qwen3:8B)  -> Yahoo Finance API
  ├── POST /news_primitive/invoke    -> NewsPrimitiveModel(Qwen3:8B)   -> Real-time News API
  └── POST /amazon_primitive/invoke  -> AmazonPrimitiveModel(Qwen3:8B) -> Amazon Search API
```

Each primitive is independently deployable and exposes a clean public API.


Note: set `RAPIDAPI_KEY` in your local `.env` or server environment. Do not commit real API keys.
