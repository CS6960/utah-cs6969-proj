from __future__ import annotations

import _env_bootstrap  # noqa: F401  -- loads backend/.env before env vars are read below

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
        .limit(50)
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


def get_price_history_for_symbols(
    symbols: list[str],
    start_date: str = "",
    end_date: str = "",
    max_rows: int = 200,
) -> dict[str, list[dict[str, Any]]]:
    normalized_symbols = _normalize_symbols(symbols)
    if not normalized_symbols:
        return {}

    query = (
        _supabase.table("stock_prices")
        .select("stock_symbol,trading_date,close")
        .in_("stock_symbol", normalized_symbols)
    )
    if start_date:
        query = query.gte("trading_date", start_date)
    if end_date:
        query = query.lte("trading_date", end_date)
    response = query.order("stock_symbol").order("trading_date").limit(max_rows).execute()
    rows = response.data or []

    history_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        symbol = str(row["stock_symbol"]).upper()
        history_by_symbol.setdefault(symbol, []).append(
            {
                "tradingDate": str(row["trading_date"]),
                "close": round(float(row["close"]), 2),
            }
        )
    return history_by_symbol


def get_price_history_for_symbol(
    symbol: str,
    start_date: str = "",
    end_date: str = "",
    max_rows: int = 50,
) -> list[dict[str, Any]]:
    history = get_price_history_for_symbols([symbol], start_date, end_date, max_rows)
    return history.get(symbol.strip().upper(), [])
