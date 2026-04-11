from __future__ import annotations

import os
from typing import Any

from supabase import Client, create_client

_supabase_url = os.getenv("SUPABASE_URL")
_supabase_key = os.getenv("SUPABASE_KEY")

if not _supabase_url or not _supabase_key:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in the environment.")

_supabase: Client = create_client(_supabase_url, _supabase_key)


def _normalize_price_row(row: dict[str, Any]) -> dict[str, Any]:
    symbol = str(row["stock_symbol"]).upper()
    close_value = float(row["close"])
    trading_date = str(row["trading_date"])

    return {
        "symbol": symbol,
        "name": symbol,
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


def _normalize_symbols(symbols: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized_symbol = symbol.strip().upper()
        if normalized_symbol and normalized_symbol not in seen:
            normalized.append(normalized_symbol)
            seen.add(normalized_symbol)
    return normalized


def get_latest_close_prices() -> dict[str, Any]:
    supabase = _supabase
    latest_trading_date = _get_latest_trading_date(supabase)
    response = (
        supabase.table("stock_prices")
        .select("stock_symbol,trading_date,close")
        .eq("trading_date", latest_trading_date)
        .order("stock_symbol")
        .limit(50)
        .execute()
    )
    rows = response.data or []

    if not rows:
        raise ValueError(f"No stock_prices rows found for trading_date={latest_trading_date}.")

    return {
        "tradingDate": latest_trading_date,
        "prices": [_normalize_price_row(row) for row in rows],
    }


def get_latest_close_prices_for_symbols(symbols: list[str]) -> dict[str, Any]:
    normalized_symbols = _normalize_symbols(symbols)
    if not normalized_symbols:
        return {"tradingDate": None, "prices": []}

    supabase = _supabase
    latest_trading_date = _get_latest_trading_date(supabase)
    response = (
        supabase.table("stock_prices")
        .select("stock_symbol,trading_date,close")
        .eq("trading_date", latest_trading_date)
        .in_("stock_symbol", normalized_symbols)
        .order("stock_symbol")
        .execute()
    )
    rows = response.data or []

    if not rows:
        raise KeyError(", ".join(normalized_symbols))

    prices_by_symbol = {
        str(row["stock_symbol"]).upper(): _normalize_price_row(row)
        for row in rows
    }
    missing = [symbol for symbol in normalized_symbols if symbol not in prices_by_symbol]
    if missing:
        raise KeyError(", ".join(missing))

    return {
        "tradingDate": latest_trading_date,
        "prices": [prices_by_symbol[symbol] for symbol in normalized_symbols],
    }


def get_latest_close_price(symbol: str) -> dict[str, Any]:
    return get_latest_close_prices_for_symbols([symbol])["prices"][0]
