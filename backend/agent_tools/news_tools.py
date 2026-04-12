"""
Real news retrieval helper for the Strategist's request_news tool (Phase 2).

Queries the news_articles Supabase table. Does NOT filter by ``relevant`` —
the agent must demonstrate noise-filtering ability. The eval framework tracks
``noise_citation_count`` to measure how many noise articles the agent cited.
"""

from __future__ import annotations

import logging
import os

import _env_bootstrap  # noqa: F401
from supabase import Client, create_client

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

_supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def query_news_articles(
    tickers: list[str],
    start_date: str = "",
    end_date: str = "",
    limit: int = 10,
) -> list[dict]:
    """
    Fetch news articles for the given tickers in the date range.

    Does NOT filter by ``relevant`` — noise articles are included so the
    Strategist can demonstrate noise-filtering ability.

    Returns list of dicts with keys: ticker, headline, body, source,
    published_at, relevant, tags.
    """
    normalized = [t.strip().upper() for t in tickers if t and t.strip()]
    if not normalized:
        return []

    q = (
        _supabase.table("news_articles")
        .select("ticker,headline,body,source,published_at,relevant,tags")
        .in_("ticker", [*normalized, "NONE"])
        .order("published_at", desc=True)
        .limit(limit)
    )

    if start_date:
        q = q.gte("published_at", start_date)
    if end_date:
        q = q.lte("published_at", end_date + "T23:59:59Z")

    result = q.execute()
    articles = result.data or []
    logger.info(
        "query_news_articles: %d articles for tickers=%s range=%s..%s",
        len(articles),
        normalized,
        start_date or "*",
        end_date or "*",
    )
    return articles
