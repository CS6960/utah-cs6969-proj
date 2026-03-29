from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.tools.yahoo_finance_news import YahooFinanceNewsTool
from langchain_core.tools import tool

from portfolio import get_price_snapshot


@tool
def get_stock_price(ticker: str) -> str:
    """
    Fetch the current stock price for a given ticker symbol.
    Input should be a stock ticker (e.g., AAPL, TSLA, MSFT).
    """
    try:
        snapshot = get_price_snapshot(ticker)
        return f"The current price of {snapshot['symbol']} is {snapshot['price']:.2f} {snapshot['currency']}."
    except KeyError:
        return f"Could not find price data for {ticker.upper()}."
    except Exception as e:
        return f"Error fetching price for {ticker}: {e!s}"


# Add more tool imports here as you create them

TOOLS = [
    DuckDuckGoSearchResults(),
    YahooFinanceNewsTool(),
    get_stock_price,
]
