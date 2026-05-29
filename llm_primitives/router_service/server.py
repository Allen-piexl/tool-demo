from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from common.ollama_client import OllamaClient

load_dotenv()

SERVICE_NAME = "PrimitiveRouterService"
DEFAULT_PRIMITIVES = [
    {
        "id": "stock",
        "name": "StockPrimitive",
        "description": "Lookup stock prices and market information.",
        "capabilities": ["stock quote", "ticker lookup", "market data"],
        "endpoint": "http://127.0.0.1:8001/invoke",
        "examples": ["What is AAPL stock price?"],
    },
    {
        "id": "news",
        "name": "NewsPrimitive",
        "description": "Search recent news and summarize current events.",
        "capabilities": ["latest news", "recent events", "news retrieval"],
        "endpoint": "http://127.0.0.1:8002/invoke",
        "examples": ["latest news about climate change"],
    },
    {
        "id": "amazon",
        "name": "AmazonPrimitive",
        "description": "Search Amazon product listings.",
        "capabilities": ["amazon search", "product search", "shopping"],
        "endpoint": "http://127.0.0.1:8003/invoke",
        "examples": ["Search Amazon wireless earbuds"],
    },
    {
        "id": "kiwi",
        "name": "KiwiBookingPrimitive",
        "description": "Search Kiwi flights and start a guided booking flow.",
        "capabilities": ["flight search", "kiwi booking", "one-way flights", "round-trip flights"],
        "endpoint": "http://127.0.0.1:8010/invoke",
        "examples": ["Find a one-way flight from SEA to JFK on 2026-06-12 for 1 adult"],
    },
]

ROUTER_PROMPT = """
You are a tool router for a Primitive-as-a-Service demo.
Available tools:
{tools}

Decide whether the user query needs a tool. Return only valid JSON, no markdown.
Schema:
{{
  "use_tool": true or false,
  "tool_id": "one available tool id or null",
  "tool_name": "tool name or null",
  "args": {{"query": "original user query"}},
  "direct_response": "answer directly if no tool is needed",
  "reason": "brief reason"
}}
""".strip()

DIRECT_ANSWER_PROMPT = """
You are the assistant behind a Primitive-as-a-Service router.
The routing layer determined that no external primitive is required for this message.
Answer the user directly, clearly, and concisely. Do not mention routing, primitives,
tools, or internal system behavior unless the user explicitly asks about them.
""".strip()


class RouterRequest(BaseModel):
    query: str = Field(..., description="Natural-language message to route")
    history: list[dict[str, str]] = Field(default_factory=list)


class RouteDecision(BaseModel):
    use_tool: bool
    tool_id: str | None = None
    tool_name: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    direct_response: str = ""
    reason: str = ""


app = FastAPI(title=SERVICE_NAME)


def registry() -> list[dict[str, Any]]:
    raw = os.getenv("PRIMITIVE_REGISTRY_JSON", "").strip()
    if not raw:
        return DEFAULT_PRIMITIVES
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list) and parsed:
            return parsed
    except json.JSONDecodeError:
        pass
    return DEFAULT_PRIMITIVES


def route_with_model(req: RouterRequest) -> RouteDecision:
    tools = [
        {
            key: primitive.get(key)
            for key in ("id", "name", "description", "capabilities", "examples")
        }
        for primitive in registry()
    ]
    client = OllamaClient(
        base_url=os.getenv("ROUTER_OLLAMA_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")),
        model=os.getenv("ROUTER_OLLAMA_MODEL", os.getenv("OLLAMA_MODEL", "qwen3:8b")),
        timeout=int(os.getenv("ROUTER_TIMEOUT_SECONDS", "120")),
    )
    prompt = ROUTER_PROMPT.format(tools=json.dumps(tools, ensure_ascii=True, indent=2))
    result = client.generate_json(prompt, req.query, req.history)
    return RouteDecision.model_validate(result)


def fallback_route(query: str) -> RouteDecision:
    q = query.lower()
    if re.search(r"\b(stock|share|price|ticker|aapl|tsla|nvda|msft)\b", q):
        return RouteDecision(
            use_tool=True,
            tool_id="stock",
            tool_name="StockPrimitive",
            args={"query": query},
            reason="The query asks for market data.",
        )
    if re.search(r"\b(flight|fly|airport|booking|kiwi|one-way|roundtrip|round-trip|ticket|airline|sea|jfk|ord|lax|sfo)\b", q):
        return RouteDecision(
            use_tool=True,
            tool_id="kiwi",
            tool_name="KiwiBookingPrimitive",
            args={"query": query},
            reason="The query asks for flight search or booking.",
        )
    if re.search(r"\b(amazon|product|buy|shopping|earbuds|laptop|headphones)\b", q):
        return RouteDecision(
            use_tool=True,
            tool_id="amazon",
            tool_name="AmazonPrimitive",
            args={"query": query},
            reason="The query asks for product search.",
        )
    if re.search(r"\b(search|latest|recent|news|find)\b", q):
        return RouteDecision(
            use_tool=True,
            tool_id="news",
            tool_name="NewsPrimitive",
            args={"query": query},
            reason="The query asks for news retrieval.",
        )
    return RouteDecision(
        use_tool=False,
        direct_response="",
        reason="No external tool is necessary.",
    )


def answer_directly(req: RouterRequest) -> str:
    client = OllamaClient(
        base_url=os.getenv("ROUTER_OLLAMA_BASE_URL", os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")),
        model=os.getenv("ROUTER_OLLAMA_MODEL", os.getenv("OLLAMA_MODEL", "qwen3:8b")),
        timeout=int(os.getenv("ROUTER_TIMEOUT_SECONDS", "120")),
    )
    messages = [{"role": "system", "content": DIRECT_ANSWER_PROMPT}]
    messages.extend(req.history)
    messages.append({"role": "user", "content": req.query})
    answer = client.chat(messages).strip()
    if not answer:
        raise ValueError("Direct answer model returned an empty response")
    return answer


@app.get("/health")
def health():
    return {"ok": True, "service": SERVICE_NAME, "registered_primitives": len(registry())}


@app.get("/metadata")
def metadata():
    return {
        "service": SERVICE_NAME,
        "description": "Routes a natural-language request to an available primitive.",
        "endpoints": {"invoke": "/invoke", "health": "/health", "metadata": "/metadata"},
        "primitives": [
            {key: primitive.get(key) for key in ("id", "name", "description", "capabilities")}
            for primitive in registry()
        ],
    }


@app.post("/invoke")
def invoke(req: RouterRequest):
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Missing query")
    req = RouterRequest(query=query, history=req.history)
    started_at = time.perf_counter()
    trace: list[dict[str, Any]] = [
        {"step": "Receive user query", "status": "done", "detail": req.query}
    ]
    try:
        decision = route_with_model(req)
        trace.append({"step": "Qwen router decision", "status": "done", "detail": decision.model_dump()})
    except Exception as exc:
        decision = fallback_route(req.query)
        trace.append({"step": "Qwen router decision", "status": "fallback", "detail": str(exc)})
        trace.append({"step": "Fallback router decision", "status": "done", "detail": decision.model_dump()})

    if not decision.use_tool:
        trace.append({"step": "Generate direct answer", "status": "running", "detail": "No primitive required."})
        try:
            answer = answer_directly(req)
        except Exception as exc:
            trace[-1] = {"step": "Generate direct answer", "status": "error", "detail": str(exc)}
            raise HTTPException(
                status_code=502,
                detail={"message": "Direct answer generation failed.", "trace": trace},
            ) from exc
        trace[-1] = {"step": "Generate direct answer", "status": "done", "detail": "Answer generated without a primitive."}
        return {
            "answer": answer,
            "decision": decision.model_dump(),
            "trace": trace,
            "latency_ms": int((time.perf_counter() - started_at) * 1000),
        }

    primitive = next(
        (
            item
            for item in registry()
            if item.get("id") == decision.tool_id or item.get("name") == decision.tool_name
        ),
        None,
    )
    if primitive is None:
        trace.append({"step": "Primitive registry lookup", "status": "error", "detail": "No matching primitive found."})
        raise HTTPException(
            status_code=500,
            detail={"message": "The router selected a primitive that is not registered.", "trace": trace},
        )

    selected = {"id": primitive.get("id"), "name": primitive.get("name")}
    trace.append({"step": "Primitive registry lookup", "status": "done", "detail": selected})
    trace.append({"step": "Invoke primitive", "status": "running", "detail": selected})
    payload = {"query": req.query, "history": req.history}
    try:
        response = requests.post(
            str(primitive["endpoint"]),
            json=payload,
            timeout=int(os.getenv("ROUTER_PRIMITIVE_TIMEOUT_SECONDS", "180")),
        )
        primitive_result = response.json()
    except requests.RequestException as exc:
        trace[-1] = {"step": "Invoke primitive", "status": "error", "detail": str(exc)}
        raise HTTPException(
            status_code=502,
            detail={"message": f"Selected {selected['name']}, but invocation failed.", "trace": trace},
        ) from exc
    except ValueError as exc:
        trace[-1] = {
            "step": "Invoke primitive",
            "status": "error",
            "detail": f"Primitive returned non-JSON response: {exc}",
        }
        raise HTTPException(status_code=502, detail={"message": "Primitive returned invalid response.", "trace": trace}) from exc

    trace[-1] = {
        "step": "Invoke primitive",
        "status": "done" if response.ok else "error",
        "detail": {"selected": selected, "status": response.status_code},
    }
    if not response.ok:
        raise HTTPException(
            status_code=502,
            detail={"message": "Primitive invocation returned an error.", "primitive_result": primitive_result, "trace": trace},
        )

    trace.append({"step": "Return final answer", "status": "done", "detail": "Primitive result returned."})
    return {
        "answer": primitive_result.get("answer", primitive_result.get("result", primitive_result)),
        "decision": decision.model_dump(),
        "selected_tool": selected,
        "primitive_result": primitive_result,
        "trace": trace,
        "latency_ms": int((time.perf_counter() - started_at) * 1000),
    }
