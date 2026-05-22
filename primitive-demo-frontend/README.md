# Primitive Demo Frontend

This Next.js app is the frontend for the LLM primitive demo. It includes four main pages:

- `/tools`: product-facing data/tool catalog.
- `/chat`: ChatGPT-like user interface where Qwen decides whether to call a backend capability.
- `/booking`: Kiwi flight search plus guided booking workflow.
- `/mas`: a realistic Equity Trading Desk MAS demo.

The backend primitives live in `../llm_primitives`. Kiwi booking is exposed as an LLM-backed primitive with extra session endpoints for the browser booking flow.

## Run Locally

Install dependencies:

```powershell
npm install
```

Create local env:

```powershell
copy .env.example .env.local
```

For local development with the Kiwi primitive running on port `8011`:

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:8b
BOOKING_PRIMITIVE_URL=http://127.0.0.1:8011
```

Start the frontend:

```powershell
npm run dev
```

Open:

```text
http://localhost:3000/tools
http://localhost:3000/chat
http://localhost:3000/booking
http://localhost:3000/mas
```

If port `3000` is already in use, Next.js may start on `3001`; use the URL printed in the terminal.

## Kiwi Booking Backend

Start the Kiwi primitive from the sibling backend folder:

```powershell
cd ../llm_primitives
python -m uvicorn kiwi_booking_primitive.server:app --host 0.0.0.0 --port 8011
```

The Kiwi primitive needs:

```env
RAPIDAPI_KEY=your_rapidapi_key_here
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b
```

It also needs Playwright Chromium installed:

```powershell
python -m playwright install chromium
```

## Server / Tunnel Setup

If the Kiwi primitive runs on a server and you expose it through a tunnel, point the frontend to the tunnel URL:

```env
BOOKING_PRIMITIVE_URL=https://your-tunnel-url
```

Restart `npm run dev` after changing `.env.local`.

## Primitive Registry

The generic `/chat` page uses `PRIMITIVE_REGISTRY_JSON` from `.env.local` or the fallback registry in `app/lib/registry.ts`.

The `/booking` page uses `BOOKING_PRIMITIVE_URL` directly because Kiwi booking has session APIs:

```text
POST /invoke
POST /sessions/open
POST /sessions/{session_id}/message
POST /sessions/{session_id}/continue
```

## MAS Page

The MAS page runs a securities-trading multi-agent workflow:

```text
Trading desk request
  -> MarketResearchAgent: frames the security and requests market data
  -> Data Access Layer: LLM decides whether external data is needed
  -> Data connector call: hidden registry maps logical connector to backend endpoint
  -> DebateAgent: generates bull case vs bear case
  -> PortfolioManagerAgent: final buy / hold / sell / no-trade decision with risk controls
```

The UI visualizes the agents, analyst debate, data access decision, and execution trace.
