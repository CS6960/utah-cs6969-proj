import logging
import math

from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.tools.yahoo_finance_news import YahooFinanceNewsTool
from langchain_core.tools import tool

from portfolio import get_live_portfolio, get_price_snapshot
from agent_tools.financial_reports_tools import list_available_financial_reports, retrieve_embedded_financial_report_info

logger = logging.getLogger(__name__)

ALLOWED_CALCULATOR_GLOBALS = {
    "__builtins__": {},
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "pow": pow,
    "sum": sum,
    "math": math,
}


@tool
def get_stock_price(ticker: str) -> str:
    """
    Fetch the current stock price for a given ticker symbol.
    Input should be a stock ticker (e.g., AAPL, TSLA, MSFT).
    """
    try:
        logger.info("get_stock_price called. ticker=%s", ticker)
        snapshot = get_price_snapshot(ticker)
        logger.info(
            "get_stock_price success. ticker=%s price=%.2f currency=%s",
            snapshot["symbol"],
            snapshot["price"],
            snapshot["currency"],
        )
        return f"The current price of {snapshot['symbol']} is {snapshot['price']:.2f} {snapshot['currency']}."
    except KeyError:
        logger.warning("get_stock_price unknown ticker. ticker=%s", ticker)
        return f"Could not find price data for {ticker.upper()}."
    except Exception as e:
        logger.exception("get_stock_price failed. ticker=%s error=%s", ticker, e)
        return f"Error fetching price for {ticker}: {e!s}"


@tool
def get_portfolio_holdings() -> str:
    """
    Return the current portfolio holdings with prices and share counts.
    Call this first to understand what the user owns before analyzing risk,
    diversification, or making recommendations.
    """
    try:
        logger.info("get_portfolio_holdings called.")
        portfolio = get_live_portfolio()
        holdings = portfolio["holdings"]
        lines = []
        for h in holdings:
            day_pct = h.get("dayChangePct")
            change_str = f"{day_pct:+.2f}%" if day_pct is not None else "N/A"
            lines.append(
                f"{h['symbol']} ({h['name']}): {h['shares']} shares @ ${h['price']:.2f} "
                f"(avg cost ${h['avgCost']:.2f}, day {change_str})"
            )
        logger.info("get_portfolio_holdings success. holdings=%d", len(holdings))
        return "PORTFOLIO HOLDINGS:\n" + "\n".join(lines)
    except Exception as e:
        logger.exception("get_portfolio_holdings failed. error=%s", e)
        return f"Error fetching portfolio: {e!s}"


@tool
def calculator(expression: str) -> str:
    """
    Evaluate a math expression for arithmetic, percentages, ratios,
    and portfolio calculations.
    """
    try:
        logger.info("calculator called. expression=%s", expression)
        result = eval(expression, ALLOWED_CALCULATOR_GLOBALS, {})  # noqa: S307
        return str(result)
    except Exception as e:
        logger.exception("calculator failed. expression=%s error=%s", expression, e)
        return f"Error evaluating expression: {e!s}"


BASE_ADVISOR_TOOLS = [
    get_portfolio_holdings,
    get_stock_price,
    calculator,
]

REPORT_RETRIEVAL_TOOLS = [
    list_available_financial_reports,
    retrieve_embedded_financial_report_info,
    calculator,
]

RETRIEVER_TOOLS = [
    get_portfolio_holdings,
    get_stock_price,
    list_available_financial_reports,
    retrieve_embedded_financial_report_info,
    calculator,
]

# Backward-compatible aliases for older agent wiring.
ADVISOR_TOOLS = BASE_ADVISOR_TOOLS
REPORT_TOOLS = REPORT_RETRIEVAL_TOOLS
