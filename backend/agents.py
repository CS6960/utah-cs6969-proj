import logging
import os
from contextvars import ContextVar
from typing import Any

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from agent_tools.tools import (
    BASE_ADVISOR_TOOLS,
    REPORT_RETRIEVAL_TOOLS,
    RETRIEVER_TOOLS,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_TRACE: ContextVar[list[dict[str, Any]] | None] = ContextVar("agent_trace", default=None)
_TOOLS_CALLED: ContextVar[list[str] | None] = ContextVar("tools_called_trace", default=None)

LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL_NAME = os.getenv("MODEL_NAME", "meta/llama-3.1-70b-instruct")

model = ChatOpenAI(
    model=MODEL_NAME,
    api_key=LLM_API_KEY,
    base_url=BASE_URL,
)


def _preview(value: Any, limit: int = 180) -> str:
    text = str(value).replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _trace(event_type: str, **payload: Any) -> None:
    trace = _TRACE.get()
    if trace is None:
        return
    event = {"type": event_type, **payload}
    trace.append(event)
    logger.info("agent_trace %s", event)


def _start_trace(role: str, query: str) -> object:
    _TOOLS_CALLED.set([])
    return _TRACE.set(
        [
            {
                "type": "agent_run_started",
                "role": role,
                "query_preview": _preview(query),
            }
        ]
    )


def _append_tools_called(*tool_names: str) -> None:
    tools_called = _TOOLS_CALLED.get()
    if tools_called is None:
        return
    tools_called.extend(tool_names)


def _end_trace(token: object) -> tuple[list[dict[str, Any]], list[str]]:
    trace = _TRACE.get() or []
    tools_called = _TOOLS_CALLED.get() or []
    _TRACE.reset(token)
    _TOOLS_CALLED.set(None)
    return trace, tools_called

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
    _trace(
        "tool_called",
        tool="call_financial_reports_retrieval_agent",
        query_preview=_preview(query),
    )
    _append_tools_called("call_financial_reports_retrieval_agent")
    result = financial_reports_retrieval_agent.invoke({"messages": [HumanMessage(content=query)]})
    response = result["messages"][-1].content
    nested_tool_calls = extract_tool_call_details(result["messages"])
    nested_tools_called = [tool_call["name"] for tool_call in nested_tool_calls]
    for tool_call in nested_tool_calls:
        _append_tools_called(tool_call["name"])
        _trace(
            "agent_tool_selection",
            role="financial_reports_retrieval_agent",
            tool=tool_call["name"],
            args=tool_call["args"],
            args_preview=tool_call["args_preview"],
            delegated_by="call_financial_reports_retrieval_agent",
        )
    _trace(
        "subagent_completed",
        role="financial_reports_retrieval_agent",
        tools_called=nested_tools_called,
        response_preview=_preview(response),
    )
    return response


@tool
def call_skeptic_response(query: str, current_analysis: str) -> str:
    """
    Generate a skeptical review that highlights risks, missing evidence,
    and weak assumptions in the current analysis.
    """
    _trace(
        "tool_called",
        tool="call_skeptic_response",
        query_preview=_preview(query),
        analysis_preview=_preview(current_analysis),
    )
    _append_tools_called("call_skeptic_response")
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
    _trace("llm_completed", role="skeptic", response_preview=_preview(result.content))
    return result.content


@tool
def call_visionary_response(query: str, current_analysis: str, skeptic_response: str) -> str:
    """
    Generate a visionary review after considering the current analysis
    and the skeptic's critique.
    """
    _trace(
        "tool_called",
        tool="call_visionary_response",
        query_preview=_preview(query),
        analysis_preview=_preview(current_analysis),
        skeptic_preview=_preview(skeptic_response),
    )
    _append_tools_called("call_visionary_response")
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
    _trace("llm_completed", role="visionary", response_preview=_preview(result.content))
    return result.content


financial_advisor_agent = create_agent(
    model,
    tools=[
        *BASE_ADVISOR_TOOLS,
        call_financial_reports_retrieval_agent,
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
        "The required order is: working analysis -> retrieval -> final answer. "
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


def extract_tool_call_details(messages: list) -> list[dict[str, Any]]:
    tool_calls: list[dict[str, Any]] = []
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                args = tc.get("args", {})
                tool_calls.append(
                    {
                        "name": tc["name"],
                        "args": args,
                        "args_preview": _preview(args),
                    }
                )
    return tool_calls


def run_agent(query: str, role: str = "financial_advisor"):
    token = _start_trace(role, query)
    agent = AGENTS.get(role, financial_advisor_agent)
    try:
        result = agent.invoke({"messages": [HumanMessage(content=query)]})
        tool_calls = extract_tool_call_details(result["messages"])
        tools_called = [tool_call["name"] for tool_call in tool_calls]
        response = result["messages"][-1].content
        for tool_call in tool_calls:
            _append_tools_called(tool_call["name"])
            _trace(
                "agent_tool_selection",
                role=role,
                tool=tool_call["name"],
                args=tool_call["args"],
                args_preview=tool_call["args_preview"],
            )
        trace, aggregated_tools_called = _end_trace(token)
        _trace(
            "agent_run_completed",
            role=role,
            tools_called=aggregated_tools_called,
            response_preview=_preview(response),
        )
        trace.append(
            {
                "type": "agent_run_completed",
                "role": role,
                "tools_called": aggregated_tools_called,
                "response_preview": _preview(response),
            }
        )
        logger.info("agent_trace %s", trace[-1])
        return response, aggregated_tools_called, trace
    except Exception as exc:
        _trace("agent_run_failed", role=role, error=repr(exc))
        _end_trace(token)
        raise
