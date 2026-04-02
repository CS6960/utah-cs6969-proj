from __future__ import annotations

import os
from datetime import date, timedelta

from dotenv import load_dotenv
from supabase import Client, create_client


load_dotenv()


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


BASE_CLOSES = {
    "AAPL": 214.65,
    "MSFT": 428.90,
    "JPM": 198.34,
    "NVDA": 118.77,
    "AMZN": 179.43,
    "GOOGL": 164.52,
    "LLY": 836.25,
    "XOM": 112.68,
}


PRICE_MOVES = {
    "AAPL": [-3.25, -1.95, -0.85, 0.00, 0.65, 1.55, 2.70],
    "MSFT": [-4.80, -2.40, -1.10, 0.00, 1.30, 2.90, 4.10],
    "JPM": [-2.25, -1.10, -0.50, 0.00, 0.55, 1.20, 1.95],
    "NVDA": [-5.10, -3.00, -1.35, 0.00, 1.75, 3.40, 5.25],
    "AMZN": [-3.60, -2.10, -0.95, 0.00, 0.70, 1.65, 2.80],
    "GOOGL": [-2.90, -1.55, -0.70, 0.00, 0.50, 1.35, 2.10],
    "LLY": [-10.50, -6.25, -3.10, 0.00, 2.85, 6.40, 9.75],
    "XOM": [-2.40, -1.35, -0.70, 0.00, 0.60, 1.25, 2.05],
}


def get_supabase_client() -> Client:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in the environment.")

    return create_client(supabase_url, supabase_key)


def build_price_rows() -> list[dict[str, object]]:
    end_date = date.today()
    trading_dates = [end_date - timedelta(days=offset) for offset in range(6, -1, -1)]
    rows: list[dict[str, object]] = []

    for stock in STOCKS:
        symbol = stock["symbol"]
        base_close = BASE_CLOSES[symbol]
        moves = PRICE_MOVES[symbol]

        for idx, trading_date in enumerate(trading_dates):
            close_price = round(base_close + moves[idx], 2)

            rows.append(
                {
                    "symbol": symbol,
                    "trading_date": trading_date.isoformat(),
                    "close": close_price,
                }
            )

    return rows


def seed_stocks(supabase: Client) -> dict[str, str]:
    response = supabase.table("stocks").upsert(STOCKS, on_conflict="symbol").execute()
    rows = response.data or []
    return {row["symbol"]: row["id"] for row in rows}


def seed_prices(supabase: Client, stock_ids: dict[str, str]) -> int:
    price_rows = build_price_rows()
    payload = [
        {
            "stock_id": stock_ids[row["symbol"]],
            "trading_date": row["trading_date"],
            "close": row["close"],
        }
        for row in price_rows
    ]

    supabase.table("stock_prices").upsert(
        payload,
        on_conflict="stock_id,trading_date",
    ).execute()

    return len(payload)


def main() -> None:
    supabase = get_supabase_client()
    stock_ids = seed_stocks(supabase)
    inserted_price_count = seed_prices(supabase, stock_ids)
    print(f"Seeded {len(stock_ids)} stocks and {inserted_price_count} daily price rows.")


if __name__ == "__main__":
    main()
