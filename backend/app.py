import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from agent import run_agent
from portfolio import get_live_holding, get_live_portfolio

app = FastAPI()

# Enable CORS
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


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "backend"}


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


@app.post("/api/agent")
async def agent_endpoint(request: Request):
    data = await request.json()
    query = data.get("query", "")
    result = run_agent(query)
    return {"result": result}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)
