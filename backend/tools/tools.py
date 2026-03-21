from backend.tools.financial_reports_tools import create_financial_report_section_map, download_financial_report, embed_financial_report_content, find_financial_report_table_of_contents, retrieve_embedded_financial_report_info
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
        return f"Error fetching price for {ticker}: {str(e)}"



ADVISOR_TOOLS = [
    DuckDuckGoSearchResults(),
    YahooFinanceNewsTool(),
    get_stock_price,
    retrieve_embedded_financial_report_info,
]

REPORT_TOOLS = [
    download_financial_report,
    find_financial_report_table_of_contents,
    create_financial_report_section_map,
    embed_financial_report_content,
    retrieve_embedded_financial_report_info,
]
