from __future__ import annotations

import atexit
import os
import re
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}
SESSION_ROUTE = re.compile(r"^/sessions/([^/]+)/(?:message|continue)$")
SESSION_DELETE_ROUTE = re.compile(r"^/sessions/([^/]+)$")


@dataclass(frozen=True)
class PrimitiveSpec:
    name: str
    module: str
    worker_port_env: str
    default_worker_port: int
    session_aware: bool = False


SPECS = {
    "stock": PrimitiveSpec("StockPrimitiveModel", "stock_primitive.server:app", "STOCK_WORKER_PORT", 18001),
    "news": PrimitiveSpec("NewsPrimitiveModel", "news_primitive.server:app", "NEWS_WORKER_PORT", 18002),
    "amazon": PrimitiveSpec("AmazonPrimitiveModel", "amazon_primitive.server:app", "AMAZON_WORKER_PORT", 18003),
    "kiwi": PrimitiveSpec(
        "KiwiBookingPrimitiveModel",
        "kiwi_booking_primitive.server:app",
        "KIWI_WORKER_PORT",
        18010,
        session_aware=True,
    ),
}


class WorkerUnavailable(RuntimeError):
    pass


class OnDemandSupervisor:
    def __init__(self, spec: PrimitiveSpec):
        self.spec = spec
        self.worker_host = os.getenv("PRIMITIVE_WORKER_HOST", "127.0.0.1")
        self.worker_port = int(os.getenv(spec.worker_port_env, str(spec.default_worker_port)))
        self.idle_timeout = float(os.getenv("PRIMITIVE_IDLE_TIMEOUT_SECONDS", "300"))
        self.session_idle_timeout = float(os.getenv("KIWI_SESSION_IDLE_TIMEOUT_SECONDS", "1800"))
        self.startup_timeout = float(os.getenv("PRIMITIVE_STARTUP_TIMEOUT_SECONDS", "30"))
        self.process: subprocess.Popen[Any] | None = None
        self.last_activity = time.monotonic()
        self.active_sessions: dict[str, float] = {}
        self.in_flight = 0
        self.lock = threading.RLock()
        self.stop_event = threading.Event()
        self.reaper: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.worker_host}:{self.worker_port}"

    def start_reaper(self) -> None:
        if self.reaper and self.reaper.is_alive():
            return
        self.stop_event.clear()
        self.reaper = threading.Thread(target=self._reap_loop, daemon=True, name=f"{self.spec.name}-reaper")
        self.reaper.start()

    def shutdown(self) -> None:
        self.stop_event.set()
        with self.lock:
            self._stop_worker_locked()

    def status(self) -> dict[str, Any]:
        with self.lock:
            self._drop_dead_worker_locked()
            self._expire_sessions_locked(time.monotonic())
            return {
                "ok": True,
                "primitive": self.spec.name,
                "mode": "on-demand-gateway",
                "worker_running": self.process is not None,
                "worker_port": self.worker_port,
                "active_sessions": len(self.active_sessions) if self.spec.session_aware else None,
            }

    def proxy(
        self,
        method: str,
        path: str,
        query: str,
        headers: dict[str, str],
        body: bytes,
    ) -> requests.Response:
        self._begin_request()
        try:
            url = f"{self.base_url}{path}"
            if query:
                url = f"{url}?{query}"
            forwarded_headers = {
                key: value
                for key, value in headers.items()
                if key.lower() not in HOP_BY_HOP_HEADERS | {"host", "content-length"}
            }
            response = requests.request(
                method,
                url,
                headers=forwarded_headers,
                data=body,
                timeout=None,
            )
            self._record_session_activity(method, path, response)
            return response
        finally:
            with self.lock:
                self.in_flight -= 1
                self.last_activity = time.monotonic()

    def _begin_request(self) -> None:
        with self.lock:
            self._drop_dead_worker_locked()
            if self.process is None:
                self._start_worker_locked()
            self.in_flight += 1
            self.last_activity = time.monotonic()

    def _start_worker_locked(self) -> None:
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            self.spec.module,
            "--host",
            self.worker_host,
            "--port",
            str(self.worker_port),
        ]
        self.process = subprocess.Popen(command, cwd=str(ROOT), env=os.environ.copy())
        deadline = time.monotonic() + self.startup_timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                self.process = None
                raise WorkerUnavailable(f"{self.spec.name} worker exited during startup")
            try:
                response = requests.get(f"{self.base_url}/health", timeout=0.5)
                if response.ok:
                    self.last_activity = time.monotonic()
                    return
            except requests.RequestException:
                pass
            time.sleep(0.1)
        self._stop_worker_locked()
        raise WorkerUnavailable(f"{self.spec.name} worker did not become ready in time")

    def _record_session_activity(self, method: str, path: str, response: requests.Response) -> None:
        if not self.spec.session_aware or response.status_code >= 400:
            return
        now = time.monotonic()
        with self.lock:
            if method == "POST" and path == "/sessions/open":
                try:
                    session_id = response.json().get("session_id")
                except ValueError:
                    session_id = None
                if session_id:
                    self.active_sessions[str(session_id)] = now
                return
            match = SESSION_ROUTE.match(path)
            if method == "POST" and match and match.group(1) in self.active_sessions:
                self.active_sessions[match.group(1)] = now
                return
            match = SESSION_DELETE_ROUTE.match(path)
            if method == "DELETE" and match:
                self.active_sessions.pop(match.group(1), None)

    def _drop_dead_worker_locked(self) -> None:
        if self.process is not None and self.process.poll() is not None:
            self.process = None
            self.active_sessions.clear()

    def _expire_sessions_locked(self, now: float) -> None:
        if not self.spec.session_aware:
            return
        expired = [
            session_id
            for session_id, accessed_at in self.active_sessions.items()
            if now - accessed_at >= self.session_idle_timeout
        ]
        for session_id in expired:
            self.active_sessions.pop(session_id, None)

    def _reap_loop(self) -> None:
        while not self.stop_event.wait(2):
            with self.lock:
                self._drop_dead_worker_locked()
                if self.process is None or self.in_flight:
                    continue
                now = time.monotonic()
                self._expire_sessions_locked(now)
                if self.spec.session_aware and self.active_sessions:
                    continue
                if now - self.last_activity >= self.idle_timeout:
                    self._stop_worker_locked()

    def _stop_worker_locked(self) -> None:
        if self.process is None:
            return
        process = self.process
        self.process = None
        self.active_sessions.clear()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


primitive_id = os.getenv("PRIMITIVE_ID", "").strip().lower()
if primitive_id not in SPECS:
    raise RuntimeError("Set PRIMITIVE_ID to one of: stock, news, amazon, kiwi")

supervisor = OnDemandSupervisor(SPECS[primitive_id])
atexit.register(supervisor.shutdown)


@asynccontextmanager
async def lifespan(_: FastAPI):
    supervisor.start_reaper()
    try:
        yield
    finally:
        supervisor.shutdown()


app = FastAPI(
    title=f"{supervisor.spec.name} On-Demand Gateway",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/health")
def health():
    return supervisor.status()


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
)
async def proxy(path: str, request: Request):
    body = await request.body()
    try:
        response = await run_in_threadpool(
            supervisor.proxy,
            request.method,
            f"/{path}",
            request.url.query,
            dict(request.headers),
            body,
        )
    except (requests.RequestException, WorkerUnavailable) as exc:
        return JSONResponse({"detail": str(exc)}, status_code=503)
    response_headers = {
        key: value
        for key, value in response.headers.items()
        if key.lower() not in HOP_BY_HOP_HEADERS | {"content-length"}
    }
    return Response(content=response.content, status_code=response.status_code, headers=response_headers)
