# Kiwi Booking Primitive

Server-side LLM-backed primitive for flight search and guided Kiwi booking form filling.

## Run on Linux server

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp .env.example .env
# edit .env and put RAPIDAPI_KEY
uvicorn server:app --host 0.0.0.0 --port 8010
```

## Test from Windows PowerShell

```powershell
curl.exe -X POST http://YOUR_SERVER_IP:8010/invoke `
  -H "Content-Type: application/json" `
  -d "{\"query\":\"Find a one-way flight from SEA to JFK on 2026-06-15 for 1 adult\"}"
```

Open a booking session after selecting a flight:

```powershell
curl.exe -X POST http://YOUR_SERVER_IP:8010/sessions/open `
  -H "Content-Type: application/json" `
  -d "{\"booking_url\":\"KIWI_BOOKING_URL_FROM_FLIGHT_RESULT\"}"
```

Send passenger info:

```powershell
curl.exe -X POST http://YOUR_SERVER_IP:8010/sessions/SESSION_ID/message `
  -H "Content-Type: application/json" `
  -d "{\"message\":\"The passenger is Haibo Jin, Chinese, male, born on 1999-01-01\"}"
```
