from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException

from common.ollama_client import OllamaClient
from common.rapidapi_client import RapidAPIClient
from common.schemas import InvokeRequest, InvokeResponse

load_dotenv()

PRIMITIVE_NAME = "AmazonPrimitiveModel"
HOST = "real-time-amazon-data.p.rapidapi.com"
PATH = "/search"

SYSTEM_PROMPT = """
You are AmazonPrimitiveModel, an independent LLM-backed tool primitive.
Your job is to extract Amazon product search arguments from the user query.
Use this API schema:
- query: product search query, required, e.g. wireless earbuds
- country: country code, optional. Default US.
- page: page number, optional. Default 1.

Return JSON with exactly this shape:
{"query":"wireless earbuds","country":"US","page":1}
"""

app = FastAPI(title=PRIMITIVE_NAME)


def build_answer(args: dict[str, Any], api_result: dict[str, Any]) -> str:
    data = api_result.get("data", {})
    return f"Amazon search result for {args.get('query')}: {data}"


@app.get("/health")
def health():
    return {"ok": True, "primitive": PRIMITIVE_NAME}


@app.post("/invoke", response_model=InvokeResponse)
def invoke(req: InvokeRequest):
    try:
        llm = OllamaClient(
            base_url=os.getenv("AMAZON_OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
        )
        args = llm.generate_json(SYSTEM_PROMPT, req.query)
        if "query" not in args or not args["query"]:
            raise ValueError("query is required")
        args.setdefault("country", "US")
        args.setdefault("page", 1)

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
