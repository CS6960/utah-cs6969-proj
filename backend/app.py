import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from agents import run_agent
from pipeline import run_pipeline
from portfolio import get_live_holding, get_live_portfolio
from stock_prices import get_latest_close_price, get_latest_close_prices

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


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "backend", "version": BUILD_VERSION}


@app.get("/api/portfolio")
def portfolio():
    try:
        return {"holdings": get_live_portfolio()}
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
    if role in (None, "financial_advisor"):
        return run_pipeline(query)
    result, tools_called = run_agent(query, role=role)
    return {"result": result, "tools_called": tools_called}


@app.post("/api/report-agent")
async def report_agent_endpoint(request: Request):
    data = await request.json()
    query = data.get("query", "")
    result, tools_called = run_agent(query, role="financial_reports_embedding_specialist")
    return {"result": result, "tools_called": tools_called}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
