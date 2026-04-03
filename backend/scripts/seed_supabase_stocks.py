from __future__ import annotations

import csv
import os
from pathlib import Path

from supabase import Client, create_client


STOCKS = [
    {"symbol": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ", "currency": "USD"},
    {"symbol": "MSFT", "name": "Microsoft Corp.", "exchange": "NASDAQ", "currency": "USD"},
    {"symbol": "JPM", "name": "JPMorgan Chase & Co.", "exchange": "NYSE", "currency": "USD"},
    {"symbol": "NVDA", "name": "NVIDIA Corp.", "exchange": "NASDAQ", "currency": "USD"},
    {"symbol": "AMZN", "name": "Amazon.com Inc.", "exchange": "NASDAQ", "currency": "USD"},
    {"symbol": "GOOGL", "name": "Alphabet Inc. Class A", "exchange": "NASDAQ", "currency": "USD"},
    {"symbol": "LLY", "name": "Eli Lilly and Co.", "exchange": "NYSE", "currency": "USD"},
    {"symbol": "XOM", "name": "Exxon Mobil Corp.", "exchange": "NYSE", "currency": "USD"},
]

DEFAULT_CSV_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "historical_stock_prices_2026-03-24_2026-03-31.csv"
)


def get_supabase_client() -> Client:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in the environment.")

    return create_client(supabase_url, supabase_key)  # noqa: SB004


def load_price_rows_from_csv(csv_path: Path) -> list[dict[str, object]]:
    if not csv_path.exists():
        raise ValueError(f"CSV file not found: {csv_path}")

    rows: list[dict[str, object]] = []

    with csv_path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)

        for row in reader:
            stock_symbol = (row.get("stock_symbol") or "").strip().upper()
            trading_date = (row.get("trading_date") or "").strip()
            close_value = row.get("close")

            if not stock_symbol or not trading_date or close_value in (None, ""):
                continue

            rows.append(
                {
                    "symbol": stock_symbol,
                    "trading_date": trading_date,
                    "close": round(float(close_value), 2),
                }
            )

    if not rows:
        raise ValueError(f"No price rows found in CSV: {csv_path}")

    return rows


def seed_stocks(supabase: Client) -> int:
    response = supabase.table("stocks").upsert(STOCKS, on_conflict="symbol").execute()
    rows = response.data or []
    return len(rows)


def seed_prices(supabase: Client, csv_path: Path) -> int:
    price_rows = load_price_rows_from_csv(csv_path)
    payload = [
        {
            "stock_symbol": row["symbol"],
            "trading_date": row["trading_date"],
            "close": row["close"],
        }
        for row in price_rows
    ]

    supabase.table("stock_prices").upsert(
        payload,
        on_conflict="stock_symbol,trading_date",
    ).execute()

    return len(payload)


def main() -> None:
    supabase = get_supabase_client()
    csv_path = DEFAULT_CSV_PATH.resolve()
    inserted_stock_count = seed_stocks(supabase)
    inserted_price_count = seed_prices(supabase, csv_path)
    print(f"Seeded {inserted_stock_count} stocks and {inserted_price_count} daily price rows from {csv_path}.")


if __name__ == "__main__":
    main()
