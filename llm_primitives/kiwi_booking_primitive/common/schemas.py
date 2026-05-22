from __future__ import annotations
from typing import Any, Optional
from pydantic import BaseModel, Field

class InvokeRequest(BaseModel):
    query: str
    history: list[dict[str, str]] = Field(default_factory=list)

class InvokeResponse(BaseModel):
    primitive: str
    decision: str
    extracted_args: dict[str, Any] = Field(default_factory=dict)
    api_result: dict[str, Any] = Field(default_factory=dict)
    answer: str

class OpenBookingRequest(BaseModel):
    booking_url: str
    headless: bool = True

class BookingMessageRequest(BaseModel):
    message: str = ""
    collected: dict[str, Any] = Field(default_factory=dict)

class BookingSessionResponse(BaseModel):
    primitive: str
    session_id: str
    status: dict[str, Any]
    collected: dict[str, Any] = Field(default_factory=dict)
    question: Optional[dict[str, Any]] = None
    answer: str = ""
