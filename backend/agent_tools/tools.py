import logging
import math

from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.tools.yahoo_finance_news import YahooFinanceNewsTool
from langchain_core.tools import tool

from portfolio import get_live_portfolio, get_price_snapshot
from stock_prices import get_price_history_for_symbol
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
def get_stock_price_history(ticker: str, start_date: str = "", end_date: str = "") -> str:
    """
    Fetch daily closing price history for a ticker between start_date and end_date.
    Dates must be ISO format YYYY-MM-DD; if both are omitted, returns all available
    history for the ticker (currently a 7-day window around the evaluation period).
    Use this to cite specific day-over-day moves and weekly percentage changes.
    """
    try:
        logger.info(
            "get_stock_price_history called. ticker=%s start=%s end=%s",
            ticker,
            start_date,
            end_date,
        )
        history = get_price_history_for_symbol(ticker, start_date, end_date)
        if not history:
            window = f" between {start_date} and {end_date}" if (start_date or end_date) else ""
            return f"No price history found for {ticker.upper()}{window}."

        first = history[0]
        last = history[-1]
        first_close = first["close"]
        last_close = last["close"]
        pct_change = ((last_close - first_close) / first_close * 100.0) if first_close else 0.0

        body = "\n".join(f"  {row['tradingDate']}: ${row['close']:.2f}" for row in history)
        logger.info(
            "get_stock_price_history success. ticker=%s rows=%d change_pct=%.2f",
            ticker.upper(),
            len(history),
            pct_change,
        )
        return (
            f"Price history for {ticker.upper()} "
            f"({first['tradingDate']} to {last['tradingDate']}, {len(history)} sessions):\n"
            f"{body}\n"
            f"  Period change: ${first_close:.2f} -> ${last_close:.2f} ({pct_change:+.2f}%)"
        )
    except Exception as e:
        logger.exception("get_stock_price_history failed. ticker=%s error=%s", ticker, e)
        return f"Error fetching price history for {ticker}: {e!s}"


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
    get_stock_price_history,
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
    get_stock_price_history,
    list_available_financial_reports,
    retrieve_embedded_financial_report_info,
    calculator,
]

# Backward-compatible aliases for older agent wiring.
ADVISOR_TOOLS = BASE_ADVISOR_TOOLS
REPORT_TOOLS = REPORT_RETRIEVAL_TOOLS
