import logging
import os

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from tools.tools import (
    BASE_ADVISOR_TOOLS,
    REPORT_RETRIEVAL_TOOLS,
    RETRIEVER_TOOLS,
)

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

financial_reports_retrieval_agent = create_agent(
    model,
    tools=REPORT_RETRIEVAL_TOOLS,
    system_prompt=(
        "You are a financial reports retrieval agent. "
        "Your job is to gather evidence from already indexed financial reports, not to give portfolio advice. "
        "Use `list_available_financial_reports` to discover available reports, then use "
        "`retrieve_embedded_financial_report_info` to fetch the most relevant passages. "
        "Return a concise retrieval summary that includes file titles, excerpts, and any retrieval limits. "
        "Do not invent report contents, report names, or retrieval output. "
        "If no indexed reports are available, say so clearly."
    ),
)


@tool
def call_financial_reports_retrieval_agent(query: str) -> str:
    """
    Delegate SEC filing and financial report retrieval to the dedicated
    financial_reports_retrieval_agent and return its evidence summary.
    """
    result = financial_reports_retrieval_agent.invoke({"messages": [HumanMessage(content=query)]})
    return result["messages"][-1].content


@tool
def call_skeptic_response(query: str, current_analysis: str) -> str:
    """
    Generate a skeptical review that highlights risks, missing evidence,
    and weak assumptions in the current analysis.
    """
    prompt = (
        f"USER QUESTION:\n{query}\n\n"
        f"CURRENT ANALYSIS:\n{current_analysis}\n\n"
        "Provide a skeptical review focused on downside risk, unsupported claims, "
        "missing evidence, and alternative explanations."
    )
    result = model.invoke(
        [
            SystemMessage(
                content=(
                    "You are a skeptical financial reviewer. "
                    "Challenge the current analysis, surface missing evidence, identify downside risks, "
                    "and point out overconfidence or unsupported claims. "
                    "Be concise, specific, and evidence-oriented."
                )
            ),
            HumanMessage(content=prompt),
        ]
    )
    return result.content


@tool
def call_visionary_response(query: str, current_analysis: str, skeptic_response: str) -> str:
    """
    Generate a visionary review after considering the current analysis
    and the skeptic's critique.
    """
    prompt = (
        f"USER QUESTION:\n{query}\n\n"
        f"CURRENT ANALYSIS:\n{current_analysis}\n\n"
        f"SKEPTIC RESPONSE:\n{skeptic_response}\n\n"
        "Provide a visionary response that adds upside scenarios, strategic opportunities, "
        "and longer-term perspectives while staying grounded in the evidence."
    )
    result = model.invoke(
        [
            SystemMessage(
                content=(
                    "You are a visionary financial reviewer. "
                    "Expand the analysis with upside scenarios, longer-term optionality, strategic opportunities, "
                    "and second-order effects that a cautious analyst might miss. "
                    "Be concise, concrete, and grounded in the provided context."
                )
            ),
            HumanMessage(content=prompt),
        ]
    )
    return result.content


financial_advisor_agent = create_agent(
    model,
    tools=[
        *BASE_ADVISOR_TOOLS,
        call_financial_reports_retrieval_agent,
        call_skeptic_response,
        call_visionary_response,
    ],
    system_prompt=(
        "You are a financial advisor assistant for a portfolio analysis application. "
        "You help the user understand their portfolio, holdings, concentration, performance, "
        "risk, and stock-specific context. "
        "You have access to the user's portfolio, including the latest retrieved real-time market data. "
        "Use the portfolio tools whenever the user asks about their holdings, allocation, performance, "
        "concentration, or stock-specific questions. "
        "For any question about SEC filings, 10-K, 10-Q, risk factors, management discussion, "
        "financial statements, or report-specific claims, you must call "
        "`call_financial_reports_retrieval_agent` and use its evidence before answering. "
        "Before finalizing any summary or recommendation, you must first draft your working analysis, "
        "then call `call_skeptic_response`, then call `call_visionary_response`, and only then produce "
        "the final answer. "
        "The required order is: working analysis -> retrieval -> skeptic -> visionary -> final answer. "
        "Your final answer should integrate both the skeptical and visionary perspectives into one coherent summary. "
        "Do not answer report-content questions from memory. "
        "Ground your answers in the available portfolio data and current market data when possible. "
        "Be clear, analytical, concise, and practical. "
        "Do not make up holdings, prices, or portfolio facts. "
        "If the available data is insufficient, say so plainly."
    ),
)

RETRIEVER_SYSTEM_PROMPT = (
    "You are a financial research retriever. Your job is to gather evidence, NOT to give advice.\n\n"
    "Given the user's question, systematically gather relevant data:\n"
    "1. ALWAYS call get_portfolio_holdings first to see what the user owns.\n"
    "2. Check stock prices for relevant holdings using get_stock_price.\n"
    "3. Use list_available_financial_reports to find SEC filings.\n"
    "4. Use retrieve_embedded_financial_report_info for relevant excerpts.\n\n"
    "Summarize findings in structured format:\n"
    "- PORTFOLIO: [holdings summary]\n"
    "- PRICE DATA: [list prices]\n"
    "- FILING EXCERPTS: [list passages with source]\n"
    "- KEY FACTS: [most important facts uncovered]\n\n"
    "Do NOT give investment advice. Only report what the data says."
)

STRATEGIST_SYSTEM_PROMPT = (
    "You are a financial strategist. You receive a user question and an evidence package "
    "gathered by a research agent.\n\n"
    "Synthesize the evidence into clear, actionable analysis:\n"
    "1. Cross-reference sources for consistency.\n"
    "2. Identify second-order effects across sectors.\n"
    "3. Cite specific evidence for each claim.\n"
    "4. Provide directional recommendations (add/hold/trim/avoid) with confidence.\n"
    "5. Be explicit about what evidence supports vs. what is uncertain."
)

retriever_agent = create_agent(
    model,
    tools=RETRIEVER_TOOLS,
    system_prompt=RETRIEVER_SYSTEM_PROMPT,
)

AGENTS = {
    "financial_advisor": financial_advisor_agent,
    "financial_reports_retrieval_agent": financial_reports_retrieval_agent,
}


def extract_tools_called(messages: list) -> list[str]:
    tools_called = []
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                tools_called.append(tc["name"])
    return tools_called


def run_agent(query: str, role: str = "financial_advisor"):
    agent = AGENTS.get(role, financial_advisor_agent)
    result = agent.invoke({"messages": [HumanMessage(content=query)]})
    tools_called = extract_tools_called(result["messages"])
    return result["messages"][-1].content, tools_called
