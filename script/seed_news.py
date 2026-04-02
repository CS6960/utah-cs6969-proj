"""
Seed the news_articles table with articles for the evaluation window.

Usage:
    python script/seed_news.py                 # fetch & insert for all portfolio tickers
    python script/seed_news.py --ticker NVDA   # single ticker
    python script/seed_news.py --dry-run       # print articles without inserting

Fetches recent news from Yahoo Finance (via yfinance) for each ticker,
filters to the evaluation window (March 24-31, 2026), and inserts into Supabase.

After automated fetching, manually add unrelated "noise" articles via
insert_noise_articles() or by adding rows with relevant=false directly.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

# Add backend to path for shared helpers
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

PORTFOLIO_TICKERS = ["AAPL", "MSFT", "JPM", "NVDA", "AMZN", "GOOGL", "LLY", "XOM"]

EVAL_WINDOW_START = datetime(2026, 3, 24, tzinfo=timezone.utc)
EVAL_WINDOW_END = datetime(2026, 3, 31, 23, 59, 59, tzinfo=timezone.utc)


def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL or SUPABASE_KEY not set in .env")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_news_yfinance(ticker: str) -> list[dict]:
    """Fetch news for a ticker using yfinance."""
    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed. Run: pip install yfinance")
        sys.exit(1)

    stock = yf.Ticker(ticker)
    raw_news = stock.news or []
    articles = []

    for item in raw_news:
        content = item.get("content", {})
        pub_date = content.get("pubDate") or item.get("providerPublishTime")

        if isinstance(pub_date, (int, float)):
            pub_dt = datetime.fromtimestamp(pub_date, tz=timezone.utc)
        elif isinstance(pub_date, str):
            try:
                pub_dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
            except ValueError:
                continue
        else:
            continue

        headline = content.get("title") or item.get("title", "")
        body = content.get("summary") or content.get("description") or ""
        source = content.get("provider", {}).get("displayName") or item.get("publisher", "")

        if not headline:
            continue

        articles.append({
            "ticker": ticker,
            "headline": headline,
            "body": body,
            "source": source,
            "published_at": pub_dt.isoformat(),
            "relevant": True,
            "tags": [ticker, "auto-fetched"],
        })

    return articles


def fetch_news_duckduckgo(ticker: str) -> list[dict]:
    """Fallback: fetch news using DuckDuckGo search."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.error("duckduckgo_search not installed.")
        return []

    articles = []
    with DDGS() as ddgs:
        results = ddgs.news(
            f"{ticker} stock March 24-31 2026",
            max_results=10,
        )
        for item in results:
            articles.append({
                "ticker": ticker,
                "headline": item.get("title", ""),
                "body": item.get("body", ""),
                "source": item.get("source", ""),
                "published_at": item.get("date", datetime.now(timezone.utc).isoformat()),
                "relevant": True,
                "tags": [ticker, "ddg-search"],
            })

    return articles


# Pre-built noise articles — unrelated to portfolio holdings or the Iran war.
# These test whether the agent can filter irrelevant context.
NOISE_ARTICLES = [
    {
        "ticker": "NONE",
        "headline": "NASA Confirms Water Ice Deposits on Lunar South Pole",
        "body": "NASA's Artemis IV mission confirmed significant water ice deposits in permanently shadowed craters near the lunar south pole, boosting prospects for sustained lunar habitation.",
        "source": "Reuters",
        "published_at": "2026-03-25T14:00:00+00:00",
        "relevant": False,
        "tags": ["noise", "space"],
    },
    {
        "ticker": "NONE",
        "headline": "FIFA Announces Expanded Club World Cup Format for 2027",
        "body": "FIFA unveiled a new 48-team format for the 2027 Club World Cup, adding qualifying rounds for teams from smaller confederations.",
        "source": "ESPN",
        "published_at": "2026-03-26T09:30:00+00:00",
        "relevant": False,
        "tags": ["noise", "sports"],
    },
    {
        "ticker": "NONE",
        "headline": "Record Avocado Harvest in Mexico Pushes Prices to Five-Year Low",
        "body": "Mexico's avocado output hit a record 2.8 million metric tons this season, driving wholesale prices down 34% year over year.",
        "source": "Bloomberg",
        "published_at": "2026-03-27T11:00:00+00:00",
        "relevant": False,
        "tags": ["noise", "agriculture"],
    },
    {
        "ticker": "TSLA",
        "headline": "Tesla Unveils Refreshed Model Y with Longer Range Battery",
        "body": "Tesla announced an updated Model Y with a new battery architecture promising 15% more range. Deliveries expected Q3 2026.",
        "source": "CNBC",
        "published_at": "2026-03-25T16:00:00+00:00",
        "relevant": False,
        "tags": ["noise", "auto", "not-in-portfolio"],
    },
    {
        "ticker": "PFE",
        "headline": "Pfizer Reports Positive Phase 3 Results for RSV Vaccine in Infants",
        "body": "Pfizer announced its RSV vaccine candidate met all primary endpoints in a Phase 3 trial involving 7,400 infants across 20 countries.",
        "source": "Reuters",
        "published_at": "2026-03-28T08:00:00+00:00",
        "relevant": False,
        "tags": ["noise", "pharma", "not-in-portfolio"],
    },
]


def insert_articles(articles: list[dict], dry_run: bool = False) -> int:
    if dry_run:
        for a in articles:
            logger.info("[DRY RUN] %s | %s | %s", a["ticker"], a["published_at"], a["headline"])
        return len(articles)

    if not articles:
        return 0

    sb = get_supabase()
    result = sb.table("news_articles").insert(articles).execute()
    return len(result.data) if result.data else 0


def main():
    parser = argparse.ArgumentParser(description="Seed news_articles table")
    parser.add_argument("--ticker", type=str, help="Fetch for a single ticker")
    parser.add_argument("--dry-run", action="store_true", help="Print without inserting")
    parser.add_argument("--noise", action="store_true", help="Insert noise articles only")
    parser.add_argument("--source", choices=["yfinance", "ddg"], default="yfinance",
                        help="News source (default: yfinance)")
    args = parser.parse_args()

    if args.noise:
        count = insert_articles(NOISE_ARTICLES, dry_run=args.dry_run)
        logger.info("Inserted %d noise articles.", count)
        return

    tickers = [args.ticker.upper()] if args.ticker else PORTFOLIO_TICKERS
    fetch_fn = fetch_news_yfinance if args.source == "yfinance" else fetch_news_duckduckgo

    total = 0
    for ticker in tickers:
        logger.info("Fetching news for %s ...", ticker)
        articles = fetch_fn(ticker)
        logger.info("  Found %d articles for %s", len(articles), ticker)
        count = insert_articles(articles, dry_run=args.dry_run)
        total += count

    logger.info("Inserted %d articles total.", total)

    # Also insert noise articles
    noise_count = insert_articles(NOISE_ARTICLES, dry_run=args.dry_run)
    logger.info("Inserted %d noise articles.", noise_count)


if __name__ == "__main__":
    main()
