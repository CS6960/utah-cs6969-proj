import logging

from tools.financial_reports_tools import list_available_financial_reports, retrieve_embedded_financial_report_info
from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.tools.yahoo_finance_news import YahooFinanceNewsTool
from langchain_core.tools import tool

from portfolio import get_price_snapshot

logger = logging.getLogger(__name__)


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
        return f"Error fetching price for {ticker}: {str(e)}"



ADVISOR_TOOLS = [
    DuckDuckGoSearchResults(),
    YahooFinanceNewsTool(),
    get_stock_price,
    list_available_financial_reports,
    retrieve_embedded_financial_report_info,
]

REPORT_TOOLS = [
    list_available_financial_reports,
    retrieve_embedded_financial_report_info,
]
