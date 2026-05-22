from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from common.ollama_client import OllamaClient
from common.rapidapi_client import RapidAPIClient
from common.schemas import InvokeRequest, InvokeResponse

load_dotenv()

PRIMITIVE_NAME = "StockPrimitiveModel"
HOST = "yahoo-finance15.p.rapidapi.com"
PATH = "/api/v1/markets/quote"

SYSTEM_PROMPT = """
You are StockPrimitiveModel, an independent LLM-backed tool primitive.
Your job is to extract the stock ticker from the user query and produce API arguments.
Use this API schema:
- ticker: stock ticker symbol, required, e.g. AAPL, NVDA, TSLA
- type: asset type, optional, one of STOCKS, ETF, CRYPTO. Default STOCKS.

Return JSON with exactly this shape:
{"ticker":"AAPL","type":"STOCKS"}
"""

app = FastAPI(title=PRIMITIVE_NAME)


def build_answer(args: dict[str, Any], api_result: dict[str, Any]) -> str:
    data = api_result.get("data", {})
    return f"Stock quote result for {args.get('ticker')}: {data}"


@app.get("/health")
def health():
    return {"ok": True, "primitive": PRIMITIVE_NAME}


@app.post("/invoke", response_model=InvokeResponse)
def invoke(req: InvokeRequest):
    try:
        llm = OllamaClient(
            base_url=os.getenv("STOCK_OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        )
        args = llm.generate_json(SYSTEM_PROMPT, req.query)
        if "ticker" not in args or not args["ticker"]:
            raise ValueError("ticker is required")
        args.setdefault("type", "STOCKS")

        rapid = RapidAPIClient()
        api_result = rapid.get(HOST, PATH, params=args)
        return InvokeResponse(
            primitive=PRIMITIVE_NAME,
            extracted_args=args,
            api_result=api_result,
            answer=build_answer(args, api_result),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")
