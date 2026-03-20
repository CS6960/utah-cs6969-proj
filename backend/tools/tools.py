from langchain_community.tools import DuckDuckGoSearchResults
from langchain_community.tools.yahoo_finance_news import YahooFinanceNewsTool
import yfinance as yf
from langchain_core.tools import tool

@tool
def get_stock_price(ticker: str) -> str:
    """
    Fetch the current stock price for a given ticker symbol.
    Input should be a stock ticker (e.g., AAPL, TSLA, MSFT).
    """
    try:
        stock = yf.Ticker(ticker)
        # Fetch the most recent 1-day history to get the latest close
        data = stock.history(period="1d")
        if data.empty:
            return f"Could not find price data for {ticker}."
        
        current_price = data['Close'].iloc[-1]
        currency = stock.info.get('currency', 'USD')
        
        return f"The current price of {ticker} is {current_price:.2f} {currency}."
    except Exception as e:
        return f"Error fetching price for {ticker}: {str(e)}"
    
# Add more tool imports here as you create them

TOOLS = [
    DuckDuckGoSearchResults(),
    YahooFinanceNewsTool(),
    get_stock_price,
]
