from __future__ import annotations

import os
from typing import Any

from supabase import Client, create_client


PORTFOLIO_HOLDINGS = [
    {
        "symbol": "AAPL",
        "name": "Apple",
        "thesis": "Consumer ecosystem moat plus services margin expansion.",
        "catalyst": "WWDC AI rollout and buyback support.",
        "risk": "iPhone replacement cycle slows if consumer demand softens.",
        "notes": ["Large-cap core", "Low turnover", "Good tax lot cushion"],
    },
    {
        "symbol": "MSFT",
        "name": "Microsoft",
        "thesis": "Cloud cash flow funds AI capex without stressing quality.",
        "catalyst": "Azure AI monetization and Copilot attach rate.",
        "risk": "Valuation is rich if enterprise AI spend pauses.",
        "notes": ["AI platform exposure", "Core compounder", "High quality"],
    },
    {
        "symbol": "JPM",
        "name": "JPMorgan",
        "thesis": "Best-in-class bank franchise with diversified earnings.",
        "catalyst": "NII resilience and capital return.",
        "risk": "Credit costs rise if macro deteriorates.",
        "notes": ["Financial ballast", "Dividend support", "Lower beta"],
    },
    {
        "symbol": "NVDA",
        "name": "NVIDIA",
        "thesis": "AI compute demand remains supply constrained.",
        "catalyst": "Blackwell ramp and inference demand.",
        "risk": "Position can become oversized after sharp rallies.",
        "notes": ["Higher volatility", "Strong momentum", "Trim candidate"],
    },
    {
        "symbol": "AMZN",
        "name": "Amazon",
        "thesis": "Retail margins and AWS cash flow support long-duration growth.",
        "catalyst": "AWS acceleration and advertising expansion.",
        "risk": "Margin upside fades if consumer spending slows.",
        "notes": ["Consumer plus cloud", "Secular growth", "Execution heavy"],
    },
    {
        "symbol": "GOOGL",
        "name": "Alphabet",
        "thesis": "Search cash flows fund AI investment without leverage stress.",
        "catalyst": "AI product adoption and cloud operating leverage.",
        "risk": "AI competition pressures search economics.",
        "notes": ["Cash-rich", "Ad cyclical", "AI optionality"],
    },
    {
        "symbol": "LLY",
        "name": "Eli Lilly",
        "thesis": "Obesity and diabetes franchise drives multi-year earnings growth.",
        "catalyst": "Manufacturing scale and expanded indications.",
        "risk": "High expectations leave little room for execution misses.",
        "notes": ["Healthcare growth", "Premium multiple", "Lower correlation"],
    },
    {
        "symbol": "XOM",
        "name": "Exxon Mobil",
        "thesis": "Cash generation and capital discipline support shareholder returns.",
        "catalyst": "Production growth and oil price support.",
        "risk": "Commodity exposure can drag if crude weakens.",
        "notes": ["Energy hedge", "Dividend support", "Cyclical"],
    },
]

_HOLDING_METADATA = {holding["symbol"]: holding for holding in PORTFOLIO_HOLDINGS}


def _get_supabase_client() -> Client:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in the environment.")

    return create_client(supabase_url, supabase_key)


def _get_latest_prices_by_symbol(supabase: Client) -> tuple[str, dict[str, dict[str, Any]]]:
    latest_date_response = (
        supabase.table("stock_prices")
        .select("trading_date")
        .order("trading_date", desc=True)
        .limit(1)
        .execute()
    )
    latest_rows = latest_date_response.data or []

    if not latest_rows:
        raise ValueError("No stock_prices rows found in Supabase.")

    latest_trading_date = latest_rows[0].get("trading_date")

    if not latest_trading_date:
        raise ValueError("Latest trading date is missing from stock_prices.")

    prices_response = (
        supabase.table("stock_prices")
        .select("stock_symbol,trading_date,close")
        .eq("trading_date", latest_trading_date)
        .execute()
    )

    prices_by_symbol: dict[str, dict[str, Any]] = {}
    for row in prices_response.data or []:
        symbol = str(row["stock_symbol"]).upper()
        prices_by_symbol[symbol] = {
            "tradingDate": str(row["trading_date"]),
            "price": round(float(row["close"]), 2),
            "currency": "USD",
        }

    return str(latest_trading_date), prices_by_symbol


def get_price_snapshot(symbol: str) -> dict[str, Any]:
    normalized_symbol = symbol.upper()
    supabase = _get_supabase_client()
    response = (
        supabase.table("stock_prices")
        .select("stock_symbol,trading_date,close")
        .eq("stock_symbol", normalized_symbol)
        .order("trading_date", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data or []

    if not rows:
        raise KeyError(normalized_symbol)

    latest_row = rows[0]
    return {
        "symbol": normalized_symbol,
        "tradingDate": str(latest_row["trading_date"]),
        "price": round(float(latest_row["close"]), 2),
        "previousClose": None,
        "currency": "USD",
        "dayChange": None,
        "dayChangePct": None,
    }


def get_live_portfolio() -> dict[str, Any]:
    supabase = _get_supabase_client()
    latest_trading_date, prices_by_symbol = _get_latest_prices_by_symbol(supabase)

    positions_response = (
        supabase.table("portfolio_positions")
        .select("stock_symbol,shares,avg_cost")
        .order("stock_symbol")
        .execute()
    )

    holdings: list[dict[str, Any]] = []
    for position in positions_response.data or []:
        symbol = str(position["stock_symbol"]).upper()
        metadata = _HOLDING_METADATA.get(
            symbol,
            {
                "symbol": symbol,
                "name": symbol,
                "thesis": "No thesis recorded.",
                "catalyst": "No catalyst recorded.",
                "risk": "No risk recorded.",
                "notes": [],
            },
        )
        latest_price = prices_by_symbol.get(symbol)

        if latest_price is None:
            raise ValueError(f"No latest stock price found for {symbol} on {latest_trading_date}.")

        holdings.append(
            {
                **metadata,
                "shares": float(position["shares"]),
                "avgCost": round(float(position["avg_cost"]), 2),
                "price": latest_price["price"],
                "currency": latest_price["currency"],
                "tradingDate": latest_price["tradingDate"],
                "dayChange": None,
                "dayChangePct": None,
            }
        )

    cash_response = supabase.table("portfolio_cash").select("currency,cash_balance").order("currency").execute()
    cash_balances = [
        {"currency": str(row["currency"]).upper(), "cashBalance": round(float(row["cash_balance"]), 2)}
        for row in (cash_response.data or [])
    ]

    return {
        "holdings": holdings,
        "cashBalances": cash_balances,
        "latestTradingDate": latest_trading_date,
    }


def get_live_holding(symbol: str) -> dict[str, Any]:
    normalized_symbol = symbol.upper()
    portfolio = get_live_portfolio()

    for holding in portfolio["holdings"]:
        if holding["symbol"] == normalized_symbol:
            return holding

    raise KeyError(normalized_symbol)
