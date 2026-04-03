from __future__ import annotations

import os
import sys
from pathlib import Path

from supabase import Client, create_client


BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from portfolio import PORTFOLIO_HOLDINGS


CASH_BALANCES = [
    {"currency": "USD", "cash_balance": 12500.00},
]


def get_supabase_client() -> Client:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in the environment.")

    return create_client(supabase_url, supabase_key)  # noqa: SB004


def seed_positions(supabase: Client) -> int:
    payload = [
        {
            "stock_symbol": holding["symbol"],
            "shares": holding["shares"],
            "avg_cost": holding["avgCost"],
        }
        for holding in PORTFOLIO_HOLDINGS
    ]

    response = supabase.table("portfolio_positions").upsert(payload, on_conflict="stock_symbol").execute()
    return len(response.data or payload)


def seed_cash(supabase: Client) -> int:
    response = supabase.table("portfolio_cash").upsert(CASH_BALANCES, on_conflict="currency").execute()
    return len(response.data or CASH_BALANCES)


def main() -> None:
    supabase = get_supabase_client()
    position_count = seed_positions(supabase)
    cash_count = seed_cash(supabase)
    print(f"Seeded {position_count} portfolio positions and {cash_count} cash rows.")


if __name__ == "__main__":
    main()
