import asyncio
import json
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


async def _run_agent_stream(
    request: Request,
    executor_fn: Callable[[], tuple],
    result_fields: list[str],
):
    """NDJSON streaming generator.

    Runs ``executor_fn`` in the default thread executor. Emits heartbeats
    every AGENT_STREAM_HEARTBEAT_SECONDS. When the executor future resolves,
    emits a ``{"event":"result", <field>: <value>, ...}`` line. On error or
    total-cap timeout, emits ``{"event":"error","detail":...}`` and closes.
    """
    loop = asyncio.get_running_loop()
    fut = loop.run_in_executor(None, executor_fn)
    started = loop.time()

    try:
        while True:
            # Non-cancelling poll: wait() does NOT cancel the future on timeout,
            # unlike asyncio.wait_for(). Executor futures can't be cancelled
            # once the thread is running, so we just observe completion.
            done, _ = await asyncio.wait({fut}, timeout=AGENT_STREAM_HEARTBEAT_SECONDS)

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

            yield json.dumps({"event": "heartbeat", "elapsed_s": elapsed}) + "\n"
    except asyncio.CancelledError:
        # Client dropped; let the coroutine unwind.
        raise


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
