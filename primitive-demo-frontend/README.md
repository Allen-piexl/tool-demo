# PrimitiveOS Demo v7

This version includes three pages:

- `/tools`: product-facing data/tool catalog.
- `/chat`: ChatGPT-like user interface where Qwen decides whether to call a backend capability.
- `/mas`: a realistic Equity Trading Desk MAS demo.

The MAS page no longer looks like a primitive-specific demo. It runs a securities-trading multi-agent workflow:

```text
Trading desk request
  ↓
MarketResearchAgent: frames the security and requests market data
  ↓
Data Access Layer: LLM decides whether external data is needed
  ↓
Data connector call: hidden registry maps logical connector to backend endpoint
  ↓
DebateAgent: generates bull case vs bear case
  ↓
PortfolioManagerAgent: final buy / hold / sell / no-trade decision with risk controls
```

The UI visualizes the agents, the analyst debate, the data access decision, and the execution trace.

## Run on Windows

```powershell
npm install
npm run dev
```

Open:

```text
http://localhost:3000/tools
http://localhost:3000/chat
http://localhost:3000/mas
```

## Environment

Create `.env` from `.env.example`:

```powershell
copy .env.example .env
```

Typical setup when Ollama and backend capabilities are on a remote server:

```env
OLLAMA_BASE_URL=http://YOUR_SERVER_IP:11434
OLLAMA_MODEL=qwen3:8b
```

The endpoint mapping stays server-side in `PRIMITIVE_REGISTRY_JSON`; the UI does not display ports.
