from __future__ import annotations

import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, TypeVar

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from common.ollama_client import OllamaClient
from common.schemas import (
    BookingMessageRequest,
    BookingSessionResponse,
    InvokeRequest,
    InvokeResponse,
    OpenBookingRequest,
)
from .kiwi_tools import call_tool
from .browser_booking import BookingSession, confirmation_question

load_dotenv()

PRIMITIVE_NAME = "KiwiBookingPrimitiveModel"
SCREENSHOT_DIR = Path("screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

SEARCH_SYSTEM_PROMPT = """
You are KiwiBookingPrimitiveModel, an independent LLM-backed tool primitive.
Your job is to understand the user's flight-search request and choose exactly one action.

Available tools:
1. search_oneway
Required args: origin, destination, date.
Optional args: adults, children, infants, cabin_class, currency, sort_by.

2. search_roundtrip
Required args: origin, destination, outbound_date, return_date.
Optional args: adults, children, infants, cabin_class, currency.

Rules:
- Airport values must be IATA airport codes, e.g. SEA, JFK, ORD.
- Dates must be YYYY-MM-DD.
- cabin_class must be ECONOMY, BUSINESS, or FIRST.
- If required information is missing, ask a short follow-up question.
- Return JSON only. No markdown.

Return exactly this shape:
{
  "decision": "ask_user" | "use_tool" | "answer_directly",
  "tool": "search_oneway" | "search_roundtrip" | "",
  "question": "",
  "answer": "",
  "args": {}
}
""".strip()

PASSENGER_SYSTEM_PROMPT = """
You are the passenger-information extractor for a Kiwi booking page.
Extract only fields that the user explicitly provided.

Supported fields:
- given_name: passport given name
- surname: passport surname
- nationality: two-letter ISO country code, e.g. CN, US, GB
- gender: male or female
- dob_day: 1-31 as string
- dob_month: 1-12 as string
- dob_year: YYYY as string
- email: contact email for booking updates
- phone: contact phone number. Preserve the country code if the user gives one, e.g. "+1 2175185414".

Return JSON only:
{
  "passenger_patch": {
    "given_name": "",
    "surname": "",
    "nationality": "",
    "gender": "",
    "dob_day": "",
    "dob_month": "",
    "dob_year": "",
    "email": "",
    "phone": ""
  }
}
Omit unknown fields or set them to empty strings.
""".strip()

app = FastAPI(title=PRIMITIVE_NAME)
app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOT_DIR)), name="screenshots")

T = TypeVar("T")


class BookingSessionRunner:
    def __init__(self, booking_url: str, headless: bool):
        self.booking_url = booking_url
        self.headless = headless
        self.session: BookingSession | None = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="kiwi-booking")

    def open(self) -> dict[str, Any]:
        def _open() -> dict[str, Any]:
            self.session = BookingSession(booking_url=self.booking_url, headless=self.headless)
            return self.session.open()

        return self.executor.submit(_open).result()

    def run(self, fn: Callable[[BookingSession], T]) -> T:
        def _run() -> T:
            if self.session is None:
                raise RuntimeError("Booking session is not open")
            return fn(self.session)

        return self.executor.submit(_run).result()

    def close(self) -> None:
        try:
            if self.session is not None:
                self.executor.submit(lambda: self.session.close()).result()
        finally:
            self.executor.shutdown(wait=False, cancel_futures=True)


SESSIONS: dict[str, BookingSessionRunner] = {}
COLLECTED: dict[str, dict[str, Any]] = {}


def llm() -> OllamaClient:
    return OllamaClient(
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        model=os.getenv("OLLAMA_MODEL", "qwen3:8b"),
    )


def _fmt_duration(minutes: Any) -> str:
    if minutes in ("", None):
        return ""
    try:
        minutes = int(minutes)
        return f"{minutes // 60}h {minutes % 60}m"
    except Exception:
        return str(minutes)


def build_flight_answer(result: dict[str, Any]) -> str:
    flights = result.get("flights", [])
    if not flights:
        return result.get("no_results_msg", "No flights found.")

    lines = [f"Found {len(flights)} flight option(s)."]
    for f in flights[:5]:
        lines.append(
            f"Option {f.get('option')} — ${f.get('price_usd')} | "
            f"{f.get('outbound_stops')} stop(s) | {_fmt_duration(f.get('outbound_duration_min'))} | "
            f"carry-on: {f.get('carry_on_bags')} | checked: {f.get('checked_bags')}"
        )
        if f.get("booking_url"):
            lines.append(f"Booking URL: {f['booking_url']}")
    lines.append("Choose an option to start guided booking.")
    return "\n".join(lines)


def normalize_search_args(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    alias = {
        "from": "origin", "to": "destination", "departure": "origin",
        "arrival": "destination", "depart_date": "date", "travel_date": "date",
        "outbound": "outbound_date", "return": "return_date", "cabin": "cabin_class",
        "passengers": "adults", "num_adults": "adults",
    }
    out: dict[str, Any] = {}
    for k, v in args.items():
        nk = alias.get(k, k)
        out[nk] = v
    for key in ["origin", "destination"]:
        if out.get(key):
            out[key] = str(out[key]).upper().strip()
    for key in ["adults", "children", "infants", "limit"]:
        if key in out and out[key] not in (None, ""):
            out[key] = int(out[key])
    out.setdefault("adults", 1)
    out.setdefault("children", 0)
    out.setdefault("infants", 0)
    out.setdefault("cabin_class", "ECONOMY")
    out.setdefault("currency", "usd")
    return out


def next_booking_question(session_id: str) -> dict[str, Any] | None:
    runner = SESSIONS[session_id]
    collected = COLLECTED[session_id]
    q = runner.run(lambda session: session.next_question(collected))
    if q is None:
        return None
    return q


def status_with_public_screenshot(status: dict[str, Any]) -> dict[str, Any]:
    status = dict(status)
    shot = status.get("screenshot")
    if shot:
        status["screenshot_url"] = "/screenshots/" + Path(shot).name
    return status


def normalize_passenger_value(field_name: str, value: str) -> str:
    value = value.strip()
    if field_name == "gender":
        lower = value.lower()
        if lower.startswith("m") or lower in {"男", "male"}:
            return "male"
        if lower.startswith("f") or lower in {"女", "female"}:
            return "female"
    if field_name in {"dob_day", "dob_month", "dob_year"}:
        return re.sub(r"\D+", "", value)
    if field_name == "nationality" and len(value) == 2:
        return value.upper()
    if field_name == "phone":
        return re.sub(r"[^\d+]+", "", value)
    return value


def is_simple_field_answer(message: str) -> bool:
    text = message.strip()
    if not text:
        return False
    if len(text) > 40:
        return False
    return not re.search(r"[,;，；]|(?:\b(?:name|surname|nationality|gender|birth|dob|passport)\b)", text, re.I)


def should_apply_patch(message: str, current_field: str | None) -> bool:
    if not message.strip():
        return False
    if current_field and is_simple_field_answer(message):
        return False
    return True


def wants_to_continue(message: str) -> bool:
    return bool(re.search(r"\b(continue|yes|ok|proceed|accept|confirm|go ahead)\b|继续|确认|接受", message, re.I))


def wants_to_go_back(message: str) -> bool:
    return bool(re.search(r"\b(back|cancel|return|search again|no)\b|返回|取消|不要", message, re.I))


@app.get("/health")
def health():
    return {"ok": True, "primitive": PRIMITIVE_NAME}


@app.post("/invoke", response_model=InvokeResponse)
def invoke(req: InvokeRequest):
    try:
        plan = llm().generate_json(SEARCH_SYSTEM_PROMPT, req.query, req.history)
        decision = plan.get("decision", "")

        if decision == "ask_user":
            return InvokeResponse(
                primitive=PRIMITIVE_NAME,
                decision=decision,
                extracted_args=plan.get("args", {}),
                api_result={},
                answer=plan.get("question") or "Could you provide more flight details?",
            )

        if decision == "answer_directly":
            return InvokeResponse(
                primitive=PRIMITIVE_NAME,
                decision=decision,
                extracted_args={},
                api_result={},
                answer=plan.get("answer", ""),
            )

        if decision != "use_tool":
            raise ValueError(f"Invalid decision: {decision}")

        tool = plan.get("tool", "")
        args = normalize_search_args(tool, plan.get("args", {}))
        result = call_tool(tool, args)
        if "error" in result:
            raise RuntimeError(result["error"])

        return InvokeResponse(
            primitive=PRIMITIVE_NAME,
            decision=decision,
            extracted_args={"tool": tool, **args},
            api_result=result,
            answer=build_flight_answer(result),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/sessions/open", response_model=BookingSessionResponse)
def open_session(req: OpenBookingRequest):
    try:
        session_id = uuid.uuid4().hex[:12]
        runner = BookingSessionRunner(booking_url=req.booking_url, headless=req.headless)
        status = runner.open()
        SESSIONS[session_id] = runner
        COLLECTED[session_id] = {}
        q = next_booking_question(session_id)
        return BookingSessionResponse(
            primitive=PRIMITIVE_NAME,
            session_id=session_id,
            status=status_with_public_screenshot(status),
            collected=COLLECTED[session_id],
            question=q,
            answer=(q or {}).get("question") or "Booking page opened.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/sessions/{session_id}/message", response_model=BookingSessionResponse)
def session_message(session_id: str, req: BookingMessageRequest):
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    try:
        collected = COLLECTED[session_id]

        message = req.message.strip()
        current_q = next_booking_question(session_id)
        current_field = (current_q or {}).get("field")
        runner = SESSIONS[session_id]

        if current_q and current_q.get("status", {}).get("step") == "confirmation":
            if wants_to_continue(message):
                status = runner.run(lambda session: session.continue_if_possible())
                if status.get("step") == "payment":
                    status = runner.run(lambda session: session.apply_collected_fields(collected))
                q = next_booking_question(session_id)
                return BookingSessionResponse(
                    primitive=PRIMITIVE_NAME,
                    session_id=session_id,
                    status=status_with_public_screenshot(status),
                    collected=collected,
                    question=q,
                    answer=(q or {}).get("question") or "Continued. Please complete payment manually.",
                )
            if wants_to_go_back(message):
                return BookingSessionResponse(
                    primitive=PRIMITIVE_NAME,
                    session_id=session_id,
                    status=status_with_public_screenshot(current_q["status"]),
                    collected=collected,
                    question=current_q,
                    answer="Booking paused. Choose another flight option or start a new search.",
                )
            return BookingSessionResponse(
                primitive=PRIMITIVE_NAME,
                session_id=session_id,
                status=status_with_public_screenshot(current_q["status"]),
                collected=collected,
                question=current_q,
                answer=runner.run(lambda session: confirmation_question(session.page)),
            )

        if message and current_field and is_simple_field_answer(message):
            collected[current_field] = normalize_passenger_value(current_field, message)

        if should_apply_patch(message, current_field):
            patch = llm().generate_json(PASSENGER_SYSTEM_PROMPT, req.message).get("passenger_patch", {})
            for k, v in patch.items():
                if v not in (None, ""):
                    collected[k] = normalize_passenger_value(k, str(v))

        q = runner.run(lambda session: session.next_question(collected))
        if q is None:
            status = runner.run(lambda session: session.apply_collected_fields(collected))
        elif q.get("field") is None:
            status = runner.run(lambda session: session.apply_collected_fields(collected))
            status = runner.run(lambda session: session.continue_if_possible())
            if status.get("step") == "payment":
                status = runner.run(lambda session: session.apply_collected_fields(collected))
            for _ in range(3):
                q_after_continue = runner.run(lambda session: session.next_question(collected))
                if (
                    not q_after_continue
                    or q_after_continue.get("field")
                    or q_after_continue["status"].get("step") in {"payment", "confirmation"}
                ):
                    break
                status = runner.run(lambda session: session.continue_if_possible())
                if status.get("step") == "payment":
                    status = runner.run(lambda session: session.apply_collected_fields(collected))
                    break
        else:
            status = q["status"] if q else runner.run(lambda session: session.snapshot_status())

        q = next_booking_question(session_id)
        answer = "Reached payment page. Please complete payment manually."
        if q and q.get("question"):
            answer = q["question"]
        elif status.get("step") == "confirmation":
            answer = runner.run(lambda session: confirmation_question(session.page))
        elif status.get("step") != "payment":
            answer = (
                f"I filled the available details, but Kiwi is still on the "
                f"{status.get('step', 'current')} step. Check the live screenshot and press Continue, "
                "or tell me what option to choose if Kiwi is asking for a confirmation."
            )

        return BookingSessionResponse(
            primitive=PRIMITIVE_NAME,
            session_id=session_id,
            status=status_with_public_screenshot(status),
            collected=collected,
            question=q,
            answer=answer,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.post("/sessions/{session_id}/continue", response_model=BookingSessionResponse)
def continue_session(session_id: str):
    if session_id not in SESSIONS:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    try:
        runner = SESSIONS[session_id]
        status = runner.run(lambda session: session.apply_collected_fields(COLLECTED[session_id]))
        if status.get("step") == "payment":
            q = next_booking_question(session_id)
            return BookingSessionResponse(
                primitive=PRIMITIVE_NAME,
                session_id=session_id,
                status=status_with_public_screenshot(status),
                collected=COLLECTED[session_id],
                question=q,
                answer="Reached payment page. Please complete payment manually.",
            )
        status = runner.run(lambda session: session.continue_if_possible())
        q = next_booking_question(session_id)
        return BookingSessionResponse(
            primitive=PRIMITIVE_NAME,
            session_id=session_id,
            status=status_with_public_screenshot(status),
            collected=COLLECTED[session_id],
            question=q,
            answer=(q or {}).get("question") or "Continued booking flow.",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")


@app.delete("/sessions/{session_id}")
def close_session(session_id: str):
    runner = SESSIONS.pop(session_id, None)
    COLLECTED.pop(session_id, None)
    if runner:
        runner.close()
    return {"ok": True, "session_id": session_id}
