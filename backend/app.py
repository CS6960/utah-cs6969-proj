import asyncio
import contextlib
import json
import logging
import secrets
import threading
from collections.abc import Callable
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

load_dotenv(Path(__file__).resolve().parent / ".env")

from agents import run_agent, run_critic_agent  # noqa: E402
from portfolio import get_live_holding, get_live_holdings, get_live_portfolio  # noqa: E402
from stock_prices import (  # noqa: E402
    get_latest_close_price,
    get_latest_close_prices,
    get_latest_close_prices_for_symbols,
)

app = FastAPI()

# Enable CORS for the SPA and local development clients hitting this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def hello():
    return {"message": "Hello, World!"}


BUILD_VERSION = "d4b474b-debug"


def _parse_symbols(symbols: str) -> list[str]:
    return [symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()]


def _key_error_detail(error: KeyError) -> str:
    return str(error.args[0]) if error.args else str(error)


@app.api_route("/api/health", methods=["GET", "HEAD"])
def health():
    return {"status": "ok", "service": "backend", "version": BUILD_VERSION}


@app.get("/api/portfolio")
def portfolio():
    try:
        return get_live_portfolio()
    except ValueError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/portfolio/holdings")
def portfolio_holdings(symbols: str):
    parsed_symbols = _parse_symbols(symbols)
    if not parsed_symbols:
        raise HTTPException(status_code=400, detail="At least one symbol is required.")
    try:
        return get_live_holdings(parsed_symbols)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {_key_error_detail(error)}") from error
    except ValueError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/portfolio/{symbol}")
def portfolio_holding(symbol: str):
    try:
        return get_live_holding(symbol)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol.upper()}") from error
    except ValueError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/stock-prices/latest")
def latest_stock_prices():
    try:
        return get_latest_close_prices()
    except ValueError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/stock-prices/latest/batch")
def latest_stock_prices_batch(symbols: str):
    parsed_symbols = _parse_symbols(symbols)
    if not parsed_symbols:
        raise HTTPException(status_code=400, detail="At least one symbol is required.")
    try:
        return get_latest_close_prices_for_symbols(parsed_symbols)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {_key_error_detail(error)}") from error
    except ValueError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


@app.get("/api/stock-prices/latest/{symbol}")
def latest_stock_price(symbol: str):
    try:
        return get_latest_close_price(symbol)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=f"Unknown symbol: {symbol.upper()}") from error
    except ValueError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error


# Total wall-clock cap for streaming endpoints. Must be < any upstream hard limit.
AGENT_STREAM_TOTAL_CAP_SECONDS = 240
# Heartbeat interval. Must be << Render's ~100s proxy idle timeout so each
# heartbeat line resets the edge timer.
AGENT_STREAM_HEARTBEAT_SECONDS = 10

STREAM_HEADERS = {
    # Tell nginx-based proxies (Render/Cloudflare edge) NOT to buffer the
    # response body — otherwise heartbeats are held until the stream closes
    # and the whole point of heartbeats is defeated.
    "X-Accel-Buffering": "no",
    # Streams are never cacheable.
    "Cache-Control": "no-cache, no-transform",
}


_STREAM_POLL_SECONDS = 1  # sub-heartbeat poll interval for prompt stage delivery


class _StageHandler(logging.Handler):
    """Logging handler that captures agent_trace records for a specific request.

    Attached to logging.getLogger("agents") for the duration of one streaming
    request and removed in the finally block. Thread-safe: uses a nonce stored
    on threading.current_thread() to filter records to this request only, which
    is bulletproof against thread-pool reuse.
    """

    def __init__(self, nonce: str, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue) -> None:
        super().__init__()
        self._nonce = nonce
        self._loop = loop
        self._queue = queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            # Filter to this request's executor thread.
            thread_nonce = getattr(threading.current_thread(), "_meridian_request_nonce", None)
            if thread_nonce != self._nonce:
                return
            # Only handle the structured agent_trace sentinel.
            # logging stores a single dict arg as record.args == the dict
            # itself (not a tuple), so we check for that case explicitly.
            if record.msg != "agent_trace %s" or not record.args:
                return
            if isinstance(record.args, dict):
                trace = record.args
            elif isinstance(record.args, (tuple, list)) and isinstance(record.args[0], dict):
                trace = record.args[0]
            else:
                return
            with contextlib.suppress(RuntimeError):
                # RuntimeError: event loop closed (orphaned thread after
                # response finished).
                self._loop.call_soon_threadsafe(self._queue.put_nowait, trace)
        except Exception:  # noqa: S110
            # Logging handlers must never raise.
            pass


async def _run_agent_stream(
    request: Request,
    executor_fn: Callable[[], tuple],
    result_fields: list[str],
):
    """NDJSON streaming generator.

    Runs ``executor_fn`` in the default thread executor. Emits stage events
    from the agent pipeline (~1s latency), heartbeats every
    AGENT_STREAM_HEARTBEAT_SECONDS when no stage event has fired. When the
    executor future resolves, emits a ``{"event":"result", <field>: <value>,
    ...}`` line. On error or total-cap timeout, emits
    ``{"event":"error","detail":...}`` and closes.
    """
    loop = asyncio.get_running_loop()
    stage_queue: asyncio.Queue = asyncio.Queue()

    # Per-request nonce for thread isolation in the shared default thread pool.
    request_nonce = secrets.token_hex(8)

    def sync_wrapper():
        current = threading.current_thread()
        current._meridian_request_nonce = request_nonce
        try:
            return executor_fn()
        finally:
            with contextlib.suppress(AttributeError):
                delattr(current, "_meridian_request_nonce")

    agents_logger = logging.getLogger("agents")
    handler = _StageHandler(request_nonce, loop, stage_queue)
    agents_logger.addHandler(handler)

    fut = loop.run_in_executor(None, sync_wrapper)
    started = loop.time()
    last_emit_at = loop.time()

    try:
        while True:
            # Non-cancelling poll at 1s so stage events surface promptly.
            # wait() does NOT cancel the future on timeout, unlike
            # asyncio.wait_for(). Executor futures can't be cancelled once the
            # thread is running, so we just observe completion.
            done, _ = await asyncio.wait({fut}, timeout=_STREAM_POLL_SECONDS)

            # Drain stage events from the queue (cap at 20/tick to avoid
            # starving the future-done check).
            drained = 0
            while drained < 20:
                try:
                    trace = stage_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
                elapsed = int(loop.time() - started)
                yield json.dumps({"event": "stage", "elapsed_s": elapsed, **trace}) + "\n"
                last_emit_at = loop.time()
                drained += 1

            if fut in done:
                try:
                    values = fut.result()
                except Exception as error:
                    yield json.dumps({"event": "error", "detail": str(error)}) + "\n"
                    return
                payload = {"event": "result"}
                for name, value in zip(result_fields, values, strict=True):
                    payload[name] = value
                yield json.dumps(payload) + "\n"
                return

            elapsed = int(loop.time() - started)

            if elapsed >= AGENT_STREAM_TOTAL_CAP_SECONDS:
                yield (
                    json.dumps(
                        {
                            "event": "error",
                            "detail": (
                                f"Pipeline exceeded {AGENT_STREAM_TOTAL_CAP_SECONDS}s "
                                "total cap. Try a shorter question."
                            ),
                        }
                    )
                    + "\n"
                )
                return

            # Critic-flagged mitigation: if the client disconnected we can
            # stop streaming. The executor thread still runs to completion
            # (unavoidable without cooperative cancellation in agent code),
            # but the generator exits promptly.
            if await request.is_disconnected():
                return

            # Heartbeat: only if no stage or heartbeat emitted recently.
            if (loop.time() - last_emit_at) >= AGENT_STREAM_HEARTBEAT_SECONDS:
                yield json.dumps({"event": "heartbeat", "elapsed_s": elapsed}) + "\n"
                last_emit_at = loop.time()
    except asyncio.CancelledError:
        # Client dropped; let the coroutine unwind.
        raise
    finally:
        agents_logger.removeHandler(handler)


@app.post("/api/agent")
async def agent_endpoint(request: Request):
    data = await request.json()
    query = data.get("query", "")
    return StreamingResponse(
        _run_agent_stream(
            request,
            lambda: run_critic_agent(query),
            ["result", "dissent", "draft", "tools_called", "execution_trace"],
        ),
        media_type="application/x-ndjson",
        headers=STREAM_HEADERS,
    )


@app.post("/api/report-agent")
async def report_agent_endpoint(request: Request):
    data = await request.json()
    query = data.get("query", "")
    return StreamingResponse(
        _run_agent_stream(
            request,
            lambda: run_agent(query, role="financial_reports_retrieval_agent"),
            ["result", "tools_called", "execution_trace"],
        ),
        media_type="application/x-ndjson",
        headers=STREAM_HEADERS,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", reload=True)
