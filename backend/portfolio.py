from __future__ import annotations

import os
from typing import Any

from supabase import Client, create_client


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
    stocks_response = supabase.table("stocks").select("symbol,name,currency").execute()

    stock_meta_by_symbol = {
        str(row["symbol"]).upper(): {
            "name": row.get("name") or str(row["symbol"]).upper(),
            "currency": row.get("currency") or "USD",
        }
        for row in (stocks_response.data or [])
    }

    holdings: list[dict[str, Any]] = []
    for position in positions_response.data or []:
        symbol = str(position["stock_symbol"]).upper()
        latest_price = prices_by_symbol.get(symbol)

        if latest_price is None:
            raise ValueError(f"No latest stock price found for {symbol} on {latest_trading_date}.")

        stock_meta = stock_meta_by_symbol.get(symbol, {"name": symbol, "currency": "USD"})
        holdings.append(
            {
                "symbol": symbol,
                "name": stock_meta["name"],
                "shares": float(position["shares"]),
                "avgCost": round(float(position["avg_cost"]), 2),
                "price": latest_price["price"],
                "currency": stock_meta["currency"],
                "tradingDate": latest_price["tradingDate"],
                "dayChange": None,
                "dayChangePct": None,
                "thesis": "",
                "catalyst": "",
                "risk": "",
                "notes": [],
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
