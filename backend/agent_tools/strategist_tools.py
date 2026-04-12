"""
Strategist-orchestrated agent tool layer (Phase 1b).

This module defines the typed EvidenceResponse contract and the three tools
the Strategist uses to gather evidence: request_filings, request_prices,
request_news. Each tool wraps a deterministic helper, populates gaps/errors
for missing or failing data, and appends both its wrapper name and the
underlying data tool name to the existing _TOOLS_CALLED ContextVar so that
the eval framework's tool-call tracking sees the data layer, not just the
wrapper layer.

Imports from agents.py are LAZY (inside function bodies) to avoid circular
imports — agents.py imports STRATEGIST_TOOLS from this module at top level.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import tool

from agent_tools.financial_reports_tools import retrieve_embedded_financial_report_info
from portfolio import get_live_portfolio
from stock_prices import get_price_history_for_symbols

logger = logging.getLogger(__name__)

# Caps used by request_filings's defense-in-depth _RAG_COUNTER check
RAG_CEILING = 3

# ---- Typed contract --------------------------------------------------------


@dataclass
class FilingExcerpt:
    title: str  # e.g., "§1A Risk Factors" (node title)
    file_title: str  # e.g., "Apple Inc. 10-K FY2025" (document file_title)
    text: str  # truncated to 800 chars by helper before serialization
    depth: int
    score: float


@dataclass
class PriceHistoryRow:
    symbol: str
    trading_date: str  # YYYY-MM-DD
    close: float


@dataclass
class NewsArticle:
    ticker: str
    headline: str
    body: str
    published_at: str
    source: str


@dataclass
class EvidenceResponse:
    scope_request: str
    filings: list[FilingExcerpt] = field(default_factory=list)
    price_history: list[PriceHistoryRow] = field(default_factory=list)
    news: list[NewsArticle] = field(default_factory=list)
    graph_connections: list[dict] = field(default_factory=list)  # Phase 3
    tools_called: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)  # NEVER None — always list
    errors: list[str] = field(default_factory=list)  # NEVER None — always list


# ---- Portfolio context (Milestone 2 cash-exclusion bug fix) ----------------


def build_portfolio_context() -> str:
    """
    Render the user's portfolio as context for the Strategist. Fixes the M2
    cash-exclusion bug: the old pipeline.py build_portfolio_context only
    iterated holdings and ignored data["cashBalances"].
    """
    data = get_live_portfolio()
    lines = ["PORTFOLIO HOLDINGS:"]
    for h in data["holdings"]:
        day_pct = h.get("dayChangePct")
        change_str = f"{day_pct:+.2f}%" if day_pct is not None else "N/A"
        lines.append(
            f"  {h['symbol']} ({h['name']}): {h['shares']:.4f} shares @ ${h['price']:.2f} "
            f"(avg cost ${h['avgCost']:.2f}, day change {change_str})"
        )
    cash_balances = data.get("cashBalances") or []
    if cash_balances:
        lines.append("CASH BALANCES:")
        for cb in cash_balances:
            lines.append(f"  {cb['currency']}: ${cb['cashBalance']:,.2f}")
    latest = data.get("latestTradingDate")
    if latest:
        lines.append(f"LATEST TRADING DATE: {latest}")
    return "\n".join(lines)


# ---- Serialization: EvidenceResponse → markdown-with-keys for the LLM -----


def serialize_for_llm(evidence: EvidenceResponse) -> str:
    """
    Render EvidenceResponse as markdown-with-key-value-lines. Llama 3.1 70B
    struggles with nested JSON — this format is more reliable. GAPS and
    ERRORS sections are ALWAYS rendered even when empty, so the Strategist
    prompt can train on their fixed positions.
    """
    lines = [f"SCOPE: {evidence.scope_request}"]
    lines.append(f"TOOLS_CALLED: {', '.join(evidence.tools_called) if evidence.tools_called else '(none)'}")
    lines.append("")

    if evidence.filings:
        lines.append(f"FILINGS ({len(evidence.filings)} excerpts):")
        for i, f in enumerate(evidence.filings, start=1):
            lines.append(f"  {i}. [{f.file_title} | {f.title} | depth={f.depth} | score={f.score:.2f}]")
            excerpt_text = f.text[:800]
            # Indent excerpt text
            for line in excerpt_text.split("\n"):
                lines.append(f"     {line}")
    else:
        lines.append("FILINGS: (none)")
    lines.append("")

    if evidence.price_history:
        # Group by symbol for readability
        by_symbol: dict[str, list[PriceHistoryRow]] = {}
        for row in evidence.price_history:
            by_symbol.setdefault(row.symbol, []).append(row)
        lines.append("PRICE_HISTORY:")
        for symbol, rows in by_symbol.items():
            rows_sorted = sorted(rows, key=lambda r: r.trading_date)
            first = rows_sorted[0]
            last = rows_sorted[-1]
            pct = ((last.close - first.close) / first.close * 100.0) if first.close else 0.0
            daily = ", ".join(f"{r.trading_date}=${r.close:.2f}" for r in rows_sorted)
            lines.append(f"  {symbol} ({first.trading_date}->{last.trading_date}, {pct:+.2f}%): {daily}")
    else:
        lines.append("PRICE_HISTORY: (none)")
    lines.append("")

    if evidence.news:
        lines.append(f"NEWS ({len(evidence.news)} articles):")
        for i, n in enumerate(evidence.news, start=1):
            lines.append(f"  {i}. [{n.ticker} | {n.source} | {n.published_at}] {n.headline}")
    else:
        lines.append("NEWS: (none)")
    lines.append("")

    lines.append("GAPS:")
    if evidence.gaps:
        for g in evidence.gaps:
            lines.append(f"  - {g}")
    else:
        lines.append("  (none)")
    lines.append("")

    lines.append("ERRORS:")
    if evidence.errors:
        for e in evidence.errors:
            lines.append(f"  - {e}")
    else:
        lines.append("  (none)")

    return "\n".join(lines)


# ---- The three Strategist tools --------------------------------------------


@tool
def request_filings(scope: str, tickers: list[str]) -> str:
    """
    Retrieve SEC 10-K filing excerpts relevant to `scope` for the given
    portfolio tickers. `scope` is a natural-language description used as
    the embedding query (e.g., "risk factors", "geopolitical exposure").
    Returns a markdown block with FILINGS, GAPS, and ERRORS sections.
    """
    # Lazy imports to avoid circular (agents imports STRATEGIST_TOOLS at module top)
    from agents import _RAG_COUNTER, _append_tools_called

    evidence = EvidenceResponse(scope_request=scope)

    try:
        # Defense-in-depth: middleware caps request_filings at 2 invocations;
        # this counter caps underlying RPC calls at 3 across all wrappers.
        current = _RAG_COUNTER.get()
        if current >= RAG_CEILING:
            evidence.errors.append(
                f"RAG ceiling reached (>= {RAG_CEILING} calls) — refusing further filing retrieval for this request"
            )
            _append_tools_called("request_filings")
            return serialize_for_llm(evidence)

        _RAG_COUNTER.set(current + 1)
        _append_tools_called("request_filings", "retrieve_embedded_financial_report_info")

        normalized_tickers = [t.strip().upper() for t in tickers if t and t.strip()]
        if not normalized_tickers:
            evidence.gaps.append("no tickers provided to request_filings")
            return serialize_for_llm(evidence)

        ticker_file_titles: dict[str, str] = {
            "AAPL": "Apple Inc. 10-K FY2025",
            "MSFT": "Microsoft Corporation 10-K FY2025",
            "GOOGL": "Alphabet Inc. 10-K FY2025",
            "AMZN": "Amazon.com, Inc. 10-K FY2025",
            "NVDA": "NVIDIA Corporation 10-K FY2025",
            "LLY": "Eli Lilly and Company 10-K FY2025",
            "JPM": "JPMorgan Chase & Co. 10-K FY2025",
            "XOM": "Exxon Mobil Corporation 10-K FY2025",
        }

        # Per-ticker RPC calls: each ticker gets its own top-K pool so every
        # requested ticker is guaranteed at least its best-matching chunks.
        # The old approach (single unfiltered top_k=8) caused winner-takes-all
        # bias where 3-5 tickers dominated all 8 slots.
        per_ticker_k = max(1, 5 // max(len(normalized_tickers), 1))
        per_ticker_k = min(per_ticker_k, 3)

        for t in normalized_tickers:
            ft_filter = ticker_file_titles.get(t, "")

            raw = retrieve_embedded_financial_report_info.invoke(
                {
                    "query": scope,
                    "top_k": per_ticker_k,
                    "file_title": ft_filter,
                }
            )

            ticker_matches: list[Any] = []
            if isinstance(raw, dict):
                if raw.get("error"):
                    evidence.gaps.append(f"no filing excerpt for {t}: {raw['error']}")
                    continue
                ticker_matches = raw.get("matches") or []

            if not ticker_matches:
                evidence.gaps.append(f"no filing excerpt for {t} in this retrieval")
                continue

            for m in ticker_matches:
                text = m.get("text") or ""
                excerpt = text[:800]
                evidence.filings.append(
                    FilingExcerpt(
                        title=str(m.get("title") or ""),
                        file_title=str(m.get("file_title") or ""),
                        text=excerpt,
                        depth=int(m.get("depth") or 0),
                        score=float(m.get("score") or 0.0),
                    )
                )

    except Exception as exc:
        logger.exception("request_filings failed: %s", exc)
        evidence.errors.append(f"request_filings exception: {type(exc).__name__}: {exc}")

    return serialize_for_llm(evidence)


@tool
def request_prices(tickers: list[str], start_date: str = "", end_date: str = "") -> str:
    """
    Retrieve daily closing prices for the given portfolio tickers in the
    date range (ISO YYYY-MM-DD). If dates are omitted, returns all
    available history. Returns a markdown block with PRICE_HISTORY, GAPS,
    and ERRORS sections.
    """
    from agents import _append_tools_called

    evidence = EvidenceResponse(scope_request=f"prices {tickers} {start_date}..{end_date}")

    try:
        _append_tools_called("request_prices", "get_price_history_for_symbols")

        normalized_tickers = [t.strip().upper() for t in tickers if t and t.strip()]
        if not normalized_tickers:
            evidence.gaps.append("no tickers provided to request_prices")
            return serialize_for_llm(evidence)

        # Single batched Supabase call — never loop per ticker (SB003)
        history_by_symbol = get_price_history_for_symbols(
            normalized_tickers, start_date=start_date, end_date=end_date, max_rows=200
        )

        for symbol in normalized_tickers:
            rows = history_by_symbol.get(symbol) or []
            if not rows:
                evidence.gaps.append(f"no price history for {symbol}")
                continue
            # Partial-history heuristic: <3 rows when no date range OR <5 when date range given
            if not start_date and not end_date and len(rows) < 3:
                evidence.gaps.append(f"partial price history for {symbol} (only {len(rows)} sessions)")
            elif (start_date or end_date) and len(rows) < 5:
                evidence.gaps.append(
                    f"partial price history for {symbol} (only {len(rows)} sessions in requested range)"
                )
            for r in rows:
                evidence.price_history.append(
                    PriceHistoryRow(
                        symbol=symbol,
                        trading_date=str(r.get("tradingDate")),
                        close=float(r.get("close") or 0.0),
                    )
                )

    except Exception as exc:
        logger.exception("request_prices failed: %s", exc)
        evidence.errors.append(f"request_prices exception: {type(exc).__name__}: {exc}")

    return serialize_for_llm(evidence)


@tool
def request_news(scope: str, tickers: list[str]) -> str:
    """
    Retrieve recent news articles relevant to `scope` for the given
    tickers. Returns a markdown block with NEWS, GAPS, and ERRORS sections.
    Articles include both relevant and noise items — evaluate each article's
    relevance to the query before citing it in your analysis.
    """
    evidence = EvidenceResponse(scope_request=f"news {tickers} : {scope}")
    try:
        from agents import _append_tools_called

        _append_tools_called("request_news", "query_news_articles")

        from agent_tools.news_tools import query_news_articles

        normalized = [t.strip().upper() for t in tickers if t and t.strip()]
        if not normalized:
            evidence.gaps.append("no tickers provided to request_news")
            return serialize_for_llm(evidence)

        articles = query_news_articles(normalized, limit=15)

        if not articles:
            evidence.gaps.append(f"no news articles found for tickers {normalized}")
        else:
            for a in articles:
                evidence.news.append(
                    NewsArticle(
                        ticker=str(a.get("ticker") or ""),
                        headline=str(a.get("headline") or ""),
                        body=str(a.get("body") or "")[:600],
                        published_at=str(a.get("published_at") or ""),
                        source=str(a.get("source") or ""),
                    )
                )

    except Exception as exc:
        logger.exception("request_news failed: %s", exc)
        evidence.errors.append(f"request_news exception: {type(exc).__name__}: {exc}")

    return serialize_for_llm(evidence)


STRATEGIST_TOOLS = [request_filings, request_prices, request_news]
