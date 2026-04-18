import asyncio
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

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


# Render's edge proxy closes upstream connections after ~100s with no response bytes,
# returning an HTML 502 page that strips CORS headers (surfacing in the browser as a
# "CORS policy" error). Cap the pipeline wall-clock below that threshold and surface
# failures as JSON HTTPException so responses always pass through the CORS middleware.
AGENT_PIPELINE_TIMEOUT_SECONDS = 85


@app.post("/api/agent")
async def agent_endpoint(request: Request):
    data = await request.json()
    query = data.get("query", "")
    loop = asyncio.get_running_loop()
    try:
        result, dissent, draft, tools_called, execution_trace = await asyncio.wait_for(
            loop.run_in_executor(None, run_critic_agent, query),
            timeout=AGENT_PIPELINE_TIMEOUT_SECONDS,
        )
    except TimeoutError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Agent pipeline exceeded {AGENT_PIPELINE_TIMEOUT_SECONDS}s. "
                "Try a shorter question or retry in a moment."
            ),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"Agent pipeline unavailable: {error!s}",
        ) from error
    return {
        "result": result,
        "dissent": dissent,
        "draft": draft,
        "tools_called": tools_called,
        "execution_trace": execution_trace,
    }


@app.post("/api/report-agent")
async def report_agent_endpoint(request: Request):
    data = await request.json()
    query = data.get("query", "")
    loop = asyncio.get_running_loop()
    try:
        result, tools_called, execution_trace = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: run_agent(query, role="financial_reports_retrieval_agent"),
            ),
            timeout=AGENT_PIPELINE_TIMEOUT_SECONDS,
        )
    except TimeoutError as error:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Report agent exceeded {AGENT_PIPELINE_TIMEOUT_SECONDS}s. Try a shorter question or retry in a moment."
            ),
        ) from error
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail=f"Report agent unavailable: {error!s}",
        ) from error
    return {"result": result, "tools_called": tools_called, "execution_trace": execution_trace}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", reload=True)
