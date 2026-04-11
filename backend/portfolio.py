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


def _normalize_symbols(symbols: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        normalized_symbol = symbol.strip().upper()
        if normalized_symbol and normalized_symbol not in seen:
            normalized.append(normalized_symbol)
            seen.add(normalized_symbol)
    return normalized


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
        .limit(50)
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


def _get_latest_prices_for_symbols(
    supabase: Client, symbols: list[str]
) -> tuple[str, dict[str, dict[str, Any]]]:
    normalized_symbols = _normalize_symbols(symbols)
    if not normalized_symbols:
        return "", {}

    latest_trading_date_response = (
        supabase.table("stock_prices")
        .select("trading_date")
        .order("trading_date", desc=True)
        .limit(1)
        .execute()
    )
    latest_rows = latest_trading_date_response.data or []

    if not latest_rows:
        raise ValueError("No stock_prices rows found in Supabase.")

    latest_trading_date = latest_rows[0].get("trading_date")
    if not latest_trading_date:
        raise ValueError("Latest trading date is missing from stock_prices.")

    prices_response = (
        supabase.table("stock_prices")
        .select("stock_symbol,trading_date,close")
        .eq("trading_date", latest_trading_date)
        .in_("stock_symbol", normalized_symbols)
        .limit(50)
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
    latest_row = get_price_snapshots([symbol])[0]
    return {
        "symbol": latest_row["symbol"],
        "tradingDate": latest_row["tradingDate"],
        "price": latest_row["price"],
        "previousClose": None,
        "currency": latest_row["currency"],
        "dayChange": None,
        "dayChangePct": None,
    }


def get_price_snapshots(symbols: list[str]) -> list[dict[str, Any]]:
    normalized_symbols = _normalize_symbols(symbols)
    if not normalized_symbols:
        return []

    latest_trading_date, prices_by_symbol = _get_latest_prices_for_symbols(_supabase, normalized_symbols)
    snapshots: list[dict[str, Any]] = []
    missing: list[str] = []

    for symbol in normalized_symbols:
        latest_price = prices_by_symbol.get(symbol)
        if latest_price is None:
            missing.append(symbol)
            continue
        snapshots.append(
            {
                "symbol": symbol,
                "tradingDate": str(latest_trading_date),
                "price": latest_price["price"],
                "previousClose": None,
                "currency": latest_price["currency"],
                "dayChange": None,
                "dayChangePct": None,
            }
        )

    if missing:
        raise KeyError(", ".join(missing))

    return snapshots


def get_live_portfolio() -> dict[str, Any]:
    supabase = _supabase
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


def get_live_holdings(symbols: list[str]) -> dict[str, Any]:
    normalized_symbols = _normalize_symbols(symbols)
    if not normalized_symbols:
        return {"holdings": [], "latestTradingDate": None}

    supabase = _supabase
    latest_trading_date, prices_by_symbol = _get_latest_prices_for_symbols(supabase, normalized_symbols)

    positions_response = (
        supabase.table("portfolio_positions")
        .select("stock_symbol,shares,avg_cost")
        .in_("stock_symbol", normalized_symbols)
        .order("stock_symbol")
        .execute()
    )
    position_rows = positions_response.data or []
    positions_by_symbol = {
        str(row["stock_symbol"]).upper(): row
        for row in position_rows
    }

    stocks_response = (
        supabase.table("stocks")
        .select("symbol,name,currency")
        .in_("symbol", normalized_symbols)
        .execute()
    )
    stock_meta_by_symbol = {
        str(row["symbol"]).upper(): {
            "name": row.get("name") or str(row["symbol"]).upper(),
            "currency": row.get("currency") or "USD",
        }
        for row in (stocks_response.data or [])
    }

    holdings: list[dict[str, Any]] = []
    missing: list[str] = []
    for symbol in normalized_symbols:
        position = positions_by_symbol.get(symbol)
        latest_price = prices_by_symbol.get(symbol)
        if position is None or latest_price is None:
            missing.append(symbol)
            continue

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

    if missing:
        raise KeyError(", ".join(missing))

    return {
        "holdings": holdings,
        "latestTradingDate": latest_trading_date,
    }


def get_live_holding(symbol: str) -> dict[str, Any]:
    return get_live_holdings([symbol])["holdings"][0]
