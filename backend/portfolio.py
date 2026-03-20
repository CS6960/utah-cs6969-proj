from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

PORTFOLIO_HOLDINGS = [
    {
        "symbol": "AAPL",
        "name": "Apple",
        "shares": 42,
        "avgCost": 184.1,
        "thesis": "Consumer ecosystem moat plus services margin expansion.",
        "catalyst": "WWDC AI rollout and buyback support.",
        "risk": "iPhone replacement cycle slows if consumer demand softens.",
        "notes": ["Large-cap core", "Low turnover", "Good tax lot cushion"],
    },
    {
        "symbol": "MSFT",
        "name": "Microsoft",
        "shares": 18,
        "avgCost": 376.84,
        "thesis": "Cloud cash flow funds AI capex without stressing quality.",
        "catalyst": "Azure AI monetization and Copilot attach rate.",
        "risk": "Valuation is rich if enterprise AI spend pauses.",
        "notes": ["AI platform exposure", "Core compounder", "High quality"],
    },
    {
        "symbol": "JPM",
        "name": "JPMorgan",
        "shares": 35,
        "avgCost": 171.42,
        "thesis": "Best-in-class bank franchise with diversified earnings.",
        "catalyst": "NII resilience and capital return.",
        "risk": "Credit costs rise if macro deteriorates.",
        "notes": ["Financial ballast", "Dividend support", "Lower beta"],
    },
    {
        "symbol": "NVDA",
        "name": "NVIDIA",
        "shares": 16,
        "avgCost": 92.33,
        "thesis": "AI compute demand remains supply constrained.",
        "catalyst": "Blackwell ramp and inference demand.",
        "risk": "Position can become oversized after sharp rallies.",
        "notes": ["Higher volatility", "Strong momentum", "Trim candidate"],
    },
    {
        "symbol": "AMZN",
        "name": "Amazon",
        "shares": 14,
        "avgCost": 163.25,
        "thesis": "Retail margins and AWS cash flow support long-duration growth.",
        "catalyst": "AWS acceleration and advertising expansion.",
        "risk": "Margin upside fades if consumer spending slows.",
        "notes": ["Consumer plus cloud", "Secular growth", "Execution heavy"],
    },
    {
        "symbol": "GOOGL",
        "name": "Alphabet",
        "shares": 20,
        "avgCost": 145.8,
        "thesis": "Search cash flows fund AI investment without leverage stress.",
        "catalyst": "AI product adoption and cloud operating leverage.",
        "risk": "AI competition pressures search economics.",
        "notes": ["Cash-rich", "Ad cyclical", "AI optionality"],
    },
    {
        "symbol": "LLY",
        "name": "Eli Lilly",
        "shares": 8,
        "avgCost": 712.4,
        "thesis": "Obesity and diabetes franchise drives multi-year earnings growth.",
        "catalyst": "Manufacturing scale and expanded indications.",
        "risk": "High expectations leave little room for execution misses.",
        "notes": ["Healthcare growth", "Premium multiple", "Lower correlation"],
    },
    {
        "symbol": "XOM",
        "name": "Exxon Mobil",
        "shares": 26,
        "avgCost": 101.7,
        "thesis": "Cash generation and capital discipline support shareholder returns.",
        "catalyst": "Production growth and oil price support.",
        "risk": "Commodity exposure can drag if crude weakens.",
        "notes": ["Energy hedge", "Dividend support", "Cyclical"],
    },
]

PRICE_DATA_PATH = Path(__file__).resolve().parent / "data" / "stock_prices.csv"


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_price_rows() -> dict[str, dict[str, Any]]:
    if not PRICE_DATA_PATH.exists():
        raise ValueError(f"Price data file not found: {PRICE_DATA_PATH}")

    prices_by_symbol: dict[str, dict[str, Any]] = {}

    with PRICE_DATA_PATH.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)

        for row in reader:
            symbol = (row.get("symbol") or "").strip().upper()

            if not symbol:
                continue

            prices_by_symbol[symbol] = {
                "price": _safe_float(row.get("price")),
                "previousClose": _safe_float(row.get("previous_close")),
                "currency": (row.get("currency") or "USD").strip() or "USD",
            }

    return prices_by_symbol


def get_price_snapshot(symbol: str) -> dict[str, Any]:
    normalized_symbol = symbol.upper()
    prices_by_symbol = _load_price_rows()
    price_row = prices_by_symbol.get(normalized_symbol)

    if price_row is None:
        raise KeyError(normalized_symbol)

    price = price_row["price"]
    previous_close = price_row["previousClose"]

    if price is None:
        raise ValueError(f"No price available for {normalized_symbol}.")

    day_change = None if previous_close in (None, 0) else round(price - previous_close, 2)
    day_change_pct = None if previous_close in (None, 0) else round((day_change / previous_close) * 100, 2)

    return {
        "symbol": normalized_symbol,
        "price": round(price, 2),
        "previousClose": None if previous_close is None else round(previous_close, 2),
        "currency": price_row["currency"],
        "dayChange": day_change,
        "dayChangePct": day_change_pct,
    }


def get_live_portfolio() -> list[dict[str, Any]]:
    holdings: list[dict[str, Any]] = []

    for base_holding in PORTFOLIO_HOLDINGS:
        snapshot = get_price_snapshot(base_holding["symbol"])

        holdings.append(
            {
                **base_holding,
                "price": snapshot["price"],
                "currency": snapshot["currency"],
                "dayChange": snapshot["dayChange"],
                "dayChangePct": snapshot["dayChangePct"],
            }
        )

    return holdings


def get_live_holding(symbol: str) -> dict[str, Any]:
    normalized_symbol = symbol.upper()

    for holding in get_live_portfolio():
        if holding["symbol"] == normalized_symbol:
            return holding

    raise KeyError(normalized_symbol)
