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
        "You are a financial reports embedding specialist. "
        "You help the user process SEC filings and other financial reports into retrieval-ready data. "
        "When relevant, use the financial report tools step by step: "
        "download the PDF, find the table of contents, create the section map, "
        "embed the report content, and retrieve the most relevant embedded passages. "
        "Be explicit about report ids, retrieval results, and any limits in the available data. "
        "Do not invent report contents or retrieval output. "
        "If a step has not been completed yet, explain which tool should be used next."
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

    return result["messages"][-1].content
