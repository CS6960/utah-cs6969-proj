import logging
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from tools.tools import ADVISOR_TOOLS, REPORT_TOOLS


logging.basicConfig(level=logging.INFO)

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME", "meta/llama-3.1-70b-instruct")

model = ChatOpenAI(
    model=MODEL_NAME,
    api_key=API_KEY,
    base_url=BASE_URL,
)

financial_advisor_agent = create_agent(
    model,
    tools=ADVISOR_TOOLS,
    system_prompt=(
        "You are a financial advisor assistant for a portfolio analysis application. "
        "You help the user understand their portfolio, holdings, concentration, performance, "
        "risk, and stock-specific context. "
        "You have access to the user's portfolio, including the latest retrieved real-time market data. "
        "Use the portfolio tools whenever the user asks about their holdings, allocation, performance, "
        "concentration, or stock-specific questions. "
        "For any question about SEC filings, 10-K, 10-Q, risk factors, management discussion, "
        "financial statements, or report-specific claims, you must call "
        "`list_available_financial_reports` first to get a valid filename, then call "
        "`retrieve_embedded_financial_report_info` before answering. "
        "Do not answer report-content questions from memory. Use retrieved passages as evidence. "
        "If no embedded report is available or no filename is known, say that clearly and ask for the "
        "report to be embedded first. "
        "Ground your answers in the available portfolio data and current market data when possible. "
        "Be clear, analytical, concise, and practical. "
        "Do not make up holdings, prices, or portfolio facts. "
        "If the available data is insufficient, say so plainly."
    ),
)

financial_reports_embedding_specialist_agent = create_agent(
    model,
    tools=REPORT_TOOLS,
    system_prompt=(
        "You are a financial reports retrieval specialist. "
        "You help the user query already indexed financial report data. "
        "Use `list_available_financial_reports` to discover available reports, then use "
        "`retrieve_embedded_financial_report_info` to retrieve the most relevant passages. "
        "The retrieval tool selects relevant document nodes, traverses the tree, and returns ranked matches. "
        "Be explicit about file titles, traversal-based retrieval results, and any limits in the available data. "
        "Do not invent report contents or retrieval output. "
        "If no indexed reports are available, say so clearly."
    ),
)

AGENTS = {
    "financial_advisor": financial_advisor_agent,
    "financial_reports_embedding_specialist": financial_reports_embedding_specialist_agent,
}


def run_agent(query: str, role: str = "financial_advisor"):
    agent = AGENTS.get(role, financial_advisor_agent)
    result = agent.invoke({
        "messages": [HumanMessage(content=query)]
    })

    # Extract tool names from intermediate messages
    tools_called = []
    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tools_called.append(tc["name"])

    return result["messages"][-1].content, tools_called
