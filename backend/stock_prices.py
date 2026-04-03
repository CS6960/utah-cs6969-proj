from __future__ import annotations

import os
from typing import Any

from supabase import Client, create_client

from portfolio import PORTFOLIO_HOLDINGS


_HOLDING_NAME_BY_SYMBOL = {holding["symbol"]: holding["name"] for holding in PORTFOLIO_HOLDINGS}


def _get_supabase_client() -> Client:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in the environment.")

    return create_client(supabase_url, supabase_key)


def _normalize_price_row(row: dict[str, Any]) -> dict[str, Any]:
    symbol = str(row["stock_symbol"]).upper()
    close_value = float(row["close"])
    trading_date = str(row["trading_date"])

    return {
        "symbol": symbol,
        "name": _HOLDING_NAME_BY_SYMBOL.get(symbol, symbol),
        "tradingDate": trading_date,
        "price": round(close_value, 2),
        "currency": "USD",
    }


def _get_latest_trading_date(supabase: Client) -> str:
    response = (
        supabase.table("stock_prices")
        .select("trading_date")
        .order("trading_date", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data or []

    if not rows:
        raise ValueError("No stock_prices rows found in Supabase.")

    latest_date = rows[0].get("trading_date")

    if not latest_date:
        raise ValueError("Latest trading date is missing from stock_prices.")

    return str(latest_date)


def get_latest_close_prices() -> dict[str, Any]:
    supabase = _get_supabase_client()
    latest_trading_date = _get_latest_trading_date(supabase)
    response = (
        supabase.table("stock_prices")
        .select("stock_symbol,trading_date,close")
        .eq("trading_date", latest_trading_date)
        .order("stock_symbol")
        .execute()
    )
    rows = response.data or []

    if not rows:
        raise ValueError(f"No stock_prices rows found for trading_date={latest_trading_date}.")

    return {
        "tradingDate": latest_trading_date,
        "prices": [_normalize_price_row(row) for row in rows],
    }


def get_latest_close_price(symbol: str) -> dict[str, Any]:
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

    return _normalize_price_row(rows[0])
