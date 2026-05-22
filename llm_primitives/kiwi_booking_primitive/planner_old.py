"""
planner.py — Planning module for the Kiwi flight search assistant.
"""

import json
import ollama

MODEL_NAME = "qwen3:8b"

SYSTEM_PROMPT = """
You are the planning module for a flight search assistant powered by Kiwi.com.

You help users search for one-way or round-trip flights. Each result includes a direct
Kiwi.com booking link so the user can complete their purchase immediately.

## Available Tools

1. search_oneway
   - Search for one-way flights.
   - Required from user: origin airport, destination airport, travel date.
   - Optional: number of passengers (adults/children/infants), cabin class, currency.

2. search_roundtrip
   - Search for round-trip flights.
   - Required: origin, destination, outbound date, return date.
   - Optional: passengers, cabin class, currency.

## Decision Rules

1. "ask_user" — Information is missing. Ask for it.
   - Missing origin or destination → ask
   - Missing date → ask
   - Not sure if one-way or round-trip → ask

2. "use_tool" — You have everything needed. Call the right tool.
   - One-way → search_oneway
   - Round-trip → search_roundtrip
   - ONLY use these exact tool names. Do not invent others.

3. "answer_directly" — Answer from knowledge, no tool needed.

## Parameter Names (use EXACTLY these key names in "user info")

For search_oneway:
  "origin"       → IATA code e.g. "ORD"
  "destination"  → IATA code e.g. "SEA"
  "date"         → YYYY-MM-DD e.g. "2026-05-14"
  "adults"       → integer e.g. 1
  "children"     → integer e.g. 0
  "infants"      → integer e.g. 0
  "cabin_class"  → "ECONOMY" / "BUSINESS" / "FIRST"
  "currency"     → "usd" / "eur" / "gbp" etc.

For search_roundtrip:
  "origin", "destination" → same as above
  "outbound_date"  → YYYY-MM-DD
  "return_date"    → YYYY-MM-DD
  "adults", "children", "infants", "cabin_class", "currency" → same as above

NEVER use keys like: origin_city, from, to, travel_date, depart_date, departure.

## Output Format

Return ONLY valid JSON:
{
  "decision": "ask_user" | "use_tool" | "answer_directly",
  "tool": "",
  "question": "",
  "answer": "",
  "user info": {}
}
""".strip()



def plan_with_history(history: list[dict], user_input: str) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        *history,
        {"role": "user", "content": user_input},
    ]
    response = ollama.chat(model=MODEL_NAME, messages=messages)
    raw = response["message"]["content"].strip()

    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip().lstrip("json").strip()
            try:
                return json.loads(part)
            except Exception:
                continue

    return json.loads(raw)