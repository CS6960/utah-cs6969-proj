from __future__ import annotations

import argparse
import csv
from pathlib import Path

import yfinance as yf


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

DEFAULT_OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "historical_stock_prices_2026-03-24_2026-03-31.csv"
)


def fetch_rows(start_date: str, end_date_exclusive: str) -> list[dict[str, str | float]]:
    rows: list[dict[str, str | float]] = []

    for stock in STOCKS:
        symbol = stock["symbol"]
        history = yf.Ticker(symbol).history(start=start_date, end=end_date_exclusive, auto_adjust=False)

        if history.empty:
            raise ValueError(f"No historical prices returned for {symbol}.")

        for trading_date, row in history.iterrows():
            close_price = row.get("Close")

            if close_price is None:
                continue

            rows.append(
                {
                    "stock_symbol": symbol,
                    "trading_date": trading_date.date().isoformat(),
                    "close": round(float(close_price), 2),
                }
            )

    rows.sort(key=lambda row: (str(row["stock_symbol"]), str(row["trading_date"])))
    return rows


def write_csv(rows: list[dict[str, str | float]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=["stock_symbol", "trading_date", "close"])
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch historical close prices for portfolio tickers and save them as CSV."
    )
    parser.add_argument("--start-date", default="2026-03-24")
    parser.add_argument(
        "--end-date-exclusive",
        default="2026-04-01",
        help="Exclusive end date required by yfinance. Use 2026-04-01 to include 2026-03-31.",
    )
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = Path(args.output).resolve()
    rows = fetch_rows(args.start_date, args.end_date_exclusive)
    write_csv(rows, output_path)
    print(f"Wrote {len(rows)} rows to {output_path}.")


if __name__ == "__main__":
    main()
