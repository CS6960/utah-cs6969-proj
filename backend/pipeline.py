from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage, SystemMessage

from agents import (
    STRATEGIST_SYSTEM_PROMPT,
    extract_tools_called,
    model,
    retriever_agent,
)
from portfolio import PORTFOLIO_HOLDINGS, get_live_portfolio
from tools.financial_reports_tools import (
    list_available_financial_reports,
    retrieve_embedded_financial_report_info,
)
from tools.tools import get_stock_price

logger = logging.getLogger(__name__)

# Ordered list of portfolio ticker symbols used by the deterministic fallback.
_PORTFOLIO_TICKERS = [h["symbol"] for h in PORTFOLIO_HOLDINGS]


@dataclass
class EvidencePackage:
    query: str
    portfolio_context: str
    evidence_text: str = ""
    filing_excerpts: list[dict] = field(default_factory=list)
    news_articles: list[dict] = field(default_factory=list)  # Phase 2
    price_data: list[dict] = field(default_factory=list)
    graph_connections: list[dict] = field(default_factory=list)  # Phase 3
    tools_called: list[str] = field(default_factory=list)


def build_portfolio_context() -> str:
    holdings = get_live_portfolio()
    lines = []
    for h in holdings:
        lines.append(
            f"{h['symbol']} ({h['name']}): {h['shares']} shares @ ${h['price']:.2f}, "
            f"avg cost ${h['avgCost']:.2f}, day change {h.get('dayChangePct', 'N/A')}%"
        )
    return "\n".join(lines)


def _truncate_at_newline(text: str, limit: int) -> str:
    """Truncate *text* to at most *limit* characters, breaking at the last newline."""
    if len(text) <= limit:
        return text
    truncated = text[:limit]
    last_newline = truncated.rfind("\n")
    if last_newline > 0:
        return truncated[:last_newline]
    return truncated


def _run_fallback(query: str) -> tuple[str, list[str]]:
    """Call retriever tools directly when the agent fails or calls no tools."""
    logger.info("Running deterministic fallback.")
    fallback_parts: list[str] = []
    tools_called: list[str] = []

    price_outputs: list[str] = []
    for ticker in _PORTFOLIO_TICKERS:
        try:
            price_outputs.append(get_stock_price.invoke({"ticker": ticker}))
        except Exception:
            logger.warning("Fallback get_stock_price failed for %s", ticker)
    if price_outputs:
        fallback_parts.append("PRICE DATA:\n" + "\n".join(price_outputs))
        tools_called.append("get_stock_price")

    try:
        reports_output = list_available_financial_reports.invoke({})
        fallback_parts.append(f"AVAILABLE REPORTS:\n{reports_output}")
        tools_called.append("list_available_financial_reports")
    except Exception:
        logger.warning("Fallback list_available_financial_reports failed.")

    try:
        excerpts_output = retrieve_embedded_financial_report_info.invoke({"query": query})
        fallback_parts.append(f"FILING EXCERPTS:\n{excerpts_output}")
        tools_called.append("retrieve_embedded_financial_report_info")
    except Exception:
        logger.warning("Fallback retrieve_embedded_financial_report_info failed.")

    evidence_text = "\n\n".join(fallback_parts)
    logger.info("Deterministic fallback complete. tools_called=%s", tools_called)
    return evidence_text, tools_called


def run_retriever(query: str, portfolio_context: str) -> EvidencePackage:
    logger.info("Retriever starting. query_preview=%s", query[:80])
    start = time.time()

    tools_called: list[str] = []
    evidence_text = ""

    human_content = f"Portfolio:\n{portfolio_context}\n\nQuestion: {query}"
    try:
        result = retriever_agent.invoke({"messages": [HumanMessage(content=human_content)]})
        tools_called = extract_tools_called(result["messages"])
        evidence_text = result["messages"][-1].content
    except Exception:
        logger.exception("Retriever agent failed — will run deterministic fallback.")

    if not tools_called:
        evidence_text, tools_called = _run_fallback(query)

    evidence_text = _truncate_at_newline(evidence_text, 4000)

    elapsed = time.time() - start
    logger.info(
        "Retriever complete. elapsed=%.1fs tools_called=%s evidence_len=%d",
        elapsed,
        tools_called,
        len(evidence_text),
    )

    return EvidencePackage(
        query=query,
        portfolio_context=portfolio_context,
        evidence_text=evidence_text,
        tools_called=tools_called,
    )


def run_strategist(query: str, evidence: EvidencePackage) -> str:
    logger.info("Strategist starting. query_preview=%s", query[:80])
    start = time.time()

    evidence_text = evidence.portfolio_context + "\n\n" + evidence.evidence_text

    result = model.invoke(
        [
            SystemMessage(content=STRATEGIST_SYSTEM_PROMPT),
            HumanMessage(content=f"QUESTION: {query}\n\nEVIDENCE PACKAGE:\n{evidence_text}"),
        ]
    )

    elapsed = time.time() - start
    logger.info(
        "Strategist complete. elapsed=%.1fs response_len=%d",
        elapsed,
        len(result.content),
    )
    return result.content


def run_pipeline(query: str) -> dict:
    logger.info("Pipeline starting. query=%s", query)
    start = time.time()

    try:
        context = build_portfolio_context()
        logger.info("Portfolio context built. length=%d", len(context))

        evidence = run_retriever(query, context)
        logger.info("Retriever complete. tools_called=%s", evidence.tools_called)

        result = run_strategist(query, evidence)

        elapsed = time.time() - start
        logger.info(
            "Pipeline complete. elapsed=%.1fs tools=%s",
            elapsed,
            evidence.tools_called,
        )

        return {"result": result, "tools_called": evidence.tools_called}
    except Exception:
        logger.exception("Pipeline failed, falling back to run_agent")
        try:
            from agents import run_agent

            result, tools_called = run_agent(query, role="financial_advisor")
            return {"result": result, "tools_called": tools_called}
        except Exception:
            logger.exception("Fallback run_agent also failed")
            return {"result": "Service temporarily unavailable.", "tools_called": []}
