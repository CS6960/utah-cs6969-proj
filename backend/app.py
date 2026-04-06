from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from agents import run_agent
from portfolio import get_live_holding, get_live_holdings, get_live_portfolio
from stock_prices import (
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


@app.get("/api/health")
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


@app.post("/api/agent")
async def agent_endpoint(request: Request):
    data = await request.json()
    query = data.get("query", "")
    role = data.get("role", "financial_advisor")
    if role is None:
        role = "financial_advisor"
    result, tools_called, execution_trace = run_agent(query, role=role)
    return {"result": result, "tools_called": tools_called, "execution_trace": execution_trace}


@app.post("/api/report-agent")
async def report_agent_endpoint(request: Request):
    data = await request.json()
    query = data.get("query", "")
    result, tools_called, execution_trace = run_agent(query, role="financial_reports_retrieval_agent")
    return {"result": result, "tools_called": tools_called, "execution_trace": execution_trace}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", reload=True)
