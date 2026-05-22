"""
kiwi_tools.py — Flight search using the Kiwi.com RapidAPI.

Endpoints:
    GET /one-way     — one-way flight search
    GET /round-trip  — round-trip flight search

Booking:
    Each result includes a direct Kiwi.com booking URL.
    Users click it to go straight to Kiwi's checkout page.
"""

import json
import os
import http.client
from urllib.parse import urlencode
RAPIDAPI_HOST = "kiwi-com-cheap-flights.p.rapidapi.com"

KIWI_BASE = "https://www.kiwi.com"


def _get(path: str) -> dict:
    rapidapi_key = os.getenv("RAPIDAPI_KEY", "")
    headers = {
        "x-rapidapi-key": rapidapi_key,
        "x-rapidapi-host": RAPIDAPI_HOST,
        "Content-Type": "application/json",
    }
    if not rapidapi_key:
        return {"error": "RAPIDAPI_KEY is not set"}
    conn = http.client.HTTPSConnection(RAPIDAPI_HOST)
    conn.request("GET", path, headers=headers)
    res = conn.getresponse()
    raw = res.read().decode("utf-8")
    conn.close()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"error": "Non-JSON response", "raw": raw[:500]}


def _build_query(**kwargs) -> str:
    clean = {k: v for k, v in kwargs.items() if v is not None and v != ""}
    return urlencode(clean)


def _parse_sector(sector: dict) -> tuple[list[dict], int, int]:
    segments = sector.get("sectorSegments") or []
    legs = []

    for seg in segments:
        if not isinstance(seg, dict):
            continue
        s = seg.get("segment") or seg
        dep_place = s.get("source", {}) if isinstance(s, dict) else {}
        arr_place = s.get("destination", {}) if isinstance(s, dict) else {}
        carrier = s.get("carrier", {}) if isinstance(s, dict) else {}

        raw_leg_duration = s.get("duration", "") if isinstance(s, dict) else ""
        legs.append({
            "airline": carrier.get("name", "") if isinstance(carrier, dict) else "",
            "airline_code": carrier.get("code", "") if isinstance(carrier, dict) else "",
            "flight_number": s.get("code", "") if isinstance(s, dict) else "",
            "from_code": dep_place.get("station", {}).get("code", "") if isinstance(dep_place, dict) else "",
            "from_name": dep_place.get("station", {}).get("name", "") if isinstance(dep_place, dict) else "",
            "departs": s.get("departureTime", {}).get("local", "") if isinstance(s.get("departureTime"), dict) else s.get("departureTime", ""),
            "to_code": arr_place.get("station", {}).get("code", "") if isinstance(arr_place, dict) else "",
            "to_name": arr_place.get("station", {}).get("name", "") if isinstance(arr_place, dict) else "",
            "arrives": s.get("arrivalTime", {}).get("local", "") if isinstance(s.get("arrivalTime"), dict) else s.get("arrivalTime", ""),
            "duration_min": _duration_to_minutes(raw_leg_duration),
            "cabin": seg.get("cabinClass", "") or (s.get("cabinClass", "") if isinstance(s, dict) else ""),
        })

    duration_min = _duration_to_minutes(sector.get("duration", ""))
    stop_count = max(0, len(legs) - 1)
    return legs, duration_min, stop_count


def _duration_to_minutes(value):
    if value in ("", None):
        return value
    try:
        numeric = int(value)
    except Exception:
        return value
    return numeric // 60 if numeric > 1440 else numeric


def _parse_itineraries(raw: dict, adults: int = 1, children: int = 0, infants: int = 0) -> dict:
    if "error" in raw:
        return raw

    itins = raw.get("itineraries", [])
    if not isinstance(itins, list):
        return {"status": "no_results", "count": 0, "flights": []}

    flights = []
    for idx, itin in enumerate(itins[:10], 1):
        if not isinstance(itin, dict):
            continue

        price_raw = itin.get("price", {})
        price = price_raw.get("amount", "N/A") if isinstance(price_raw, dict) else str(price_raw)

        booking_url = ""
        try:
            edges = itin["bookingOptions"]["edges"]
            if edges:
                rel_url = edges[0]["node"]["bookingUrl"]
                booking_url = KIWI_BASE + rel_url
        except Exception:
            booking_url = ""

        outbound = itin.get("outbound") or itin.get("sector") or {}
        outbound_legs, outbound_duration, outbound_stops = _parse_sector(outbound)

        inbound = itin.get("inbound")
        inbound_legs, inbound_duration, inbound_stops = ([], "", 0)
        if isinstance(inbound, dict):
            inbound_legs, inbound_duration, inbound_stops = _parse_sector(inbound)

        bags_info = itin.get("bagsInfo", {})
        carry_on = bags_info.get("includedHandBags", 0) if isinstance(bags_info, dict) else 0
        checked = bags_info.get("includedCheckedBags", 0) if isinstance(bags_info, dict) else 0

        flights.append({
            "option": idx,
            "price_usd": price,
            "is_roundtrip": bool(inbound_legs),
            "outbound_duration_min": outbound_duration,
            "outbound_stops": outbound_stops,
            "inbound_duration_min": inbound_duration,
            "inbound_stops": inbound_stops,
            "carry_on_bags": carry_on,
            "checked_bags": checked,
            "provider": itin.get("provider", {}).get("name", "Kiwi.com") if isinstance(itin.get("provider"), dict) else "Kiwi.com",
            "booking_url": booking_url,
            "outbound_legs": outbound_legs,
            "inbound_legs": inbound_legs,
        })

    return {
        "status": "ok" if flights else "no_results",
        "count": len(flights),
        "flights": flights,
    }


def search_oneway(
    origin: str,
    destination: str,
    date: str,
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    cabin_class: str = "ECONOMY",
    currency: str = "usd",
    sort_by: str = "PRICE",
    limit: int = 10,
) -> dict:
    import time, datetime

    try:
        dt = datetime.datetime.strptime(date, "%Y-%m-%d")
        ts = int(dt.timestamp())
    except ValueError:
        ts = int(time.time()) + 86400

    query = _build_query(
        source=f"Airport:{origin.upper()}",
        destination=f"Airport:{destination.upper()}",
        outboundDepartDateFrom=ts,
        outboundDepartDateTo=ts + 86399,
        currency=currency,
        locale="en",
        adults=adults,
        children=children,
        infants=infants,
        cabinClass=cabin_class,
        sortBy=sort_by,
        sortOrder="ASCENDING",
        limit=limit,
        transportTypes="FLIGHT",
    )
    return _parse_itineraries(_get(f"/one-way?{query}"), adults, children, infants)


def search_roundtrip(
    origin: str,
    destination: str,
    outbound_date: str,
    return_date: str,
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    cabin_class: str = "ECONOMY",
    currency: str = "usd",
    limit: int = 10,
) -> dict:
    import datetime

    def _ts(d: str) -> int:
        return int(datetime.datetime.strptime(d, "%Y-%m-%d").timestamp())

    out_ts = _ts(outbound_date)
    ret_ts = _ts(return_date)

    query = _build_query(
        source=f"Airport:{origin.upper()}",
        destination=f"Airport:{destination.upper()}",
        outboundDepartDateFrom=out_ts,
        outboundDepartDateTo=out_ts + 86399,
        inboundDepartDateFrom=ret_ts,
        inboundDepartDateTo=ret_ts + 86399,
        currency=currency,
        locale="en",
        adults=adults,
        children=children,
        infants=infants,
        cabinClass=cabin_class,
        sortBy="PRICE",
        sortOrder="ASCENDING",
        limit=limit,
        transportTypes="FLIGHT",
    )
    return _parse_itineraries(_get(f"/round-trip?{query}"), adults, children, infants)


TOOL_REGISTRY = {
    "search_oneway": {"fn": search_oneway, "params": [
        {"name": "origin", "type": "string", "required": True},
        {"name": "destination", "type": "string", "required": True},
        {"name": "date", "type": "string", "required": True},
        {"name": "adults", "type": "integer", "required": False},
        {"name": "children", "type": "integer", "required": False},
        {"name": "infants", "type": "integer", "required": False},
        {"name": "cabin_class", "type": "string", "required": False},
        {"name": "currency", "type": "string", "required": False},
        {"name": "sort_by", "type": "string", "required": False},
    ]},
    "search_roundtrip": {"fn": search_roundtrip, "params": [
        {"name": "origin", "type": "string", "required": True},
        {"name": "destination", "type": "string", "required": True},
        {"name": "outbound_date", "type": "string", "required": True},
        {"name": "return_date", "type": "string", "required": True},
        {"name": "adults", "type": "integer", "required": False},
        {"name": "children", "type": "integer", "required": False},
        {"name": "infants", "type": "integer", "required": False},
        {"name": "cabin_class", "type": "string", "required": False},
        {"name": "currency", "type": "string", "required": False},
    ]},
}


def call_tool(tool_name: str, args: dict) -> dict:
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Unknown tool: '{tool_name}'"}
    try:
        return TOOL_REGISTRY[tool_name]["fn"](**args)
    except TypeError as e:
        return {"error": f"Bad arguments for {tool_name}: {e}"}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
