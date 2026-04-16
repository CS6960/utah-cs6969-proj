import logging
import os
import re
from contextvars import ContextVar
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware, ToolCallLimitMiddleware
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

import _env_bootstrap  # noqa: F401  -- loads backend/.env before env vars are read below
from agent_tools.strategist_tools import STRATEGIST_TOOLS, build_portfolio_context
from agent_tools.tools import REPORT_RETRIEVAL_TOOLS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_TRACE: ContextVar[list[dict[str, Any]] | None] = ContextVar("agent_trace", default=None)
_TOOLS_CALLED: ContextVar[list[str] | None] = ContextVar("tools_called_trace", default=None)
_RAG_COUNTER: ContextVar[int] = ContextVar("rag_counter", default=0)

LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or os.getenv("BASE_URL")
LLM_MODEL_NAME = os.getenv("LLM_MODEL_NAME") or os.getenv("MODEL_NAME", "meta/llama-3.1-70b-instruct")

model = ChatOpenAI(
    model=LLM_MODEL_NAME,
    api_key=LLM_API_KEY,
    base_url=LLM_BASE_URL,
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
    _RAG_COUNTER.set(0)
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
    _RAG_COUNTER.set(0)
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

RETRIEVER_AGENT_PROMPT = """You are Meridian's Retriever agent. Your only job is to gather evidence with the four tools provided.
You DO NOT produce analysis, recommendations, or investment advice. Your final message may be a brief
sentence noting you have completed retrieval; downstream agents will synthesize the evidence.

TIMEZONE: America/Denver.

WORKFLOW (you MUST follow this order):

1. Read the user's question.
2. Decompose it into evidence needs. Every portfolio-level question requires ALL THREE tools:
   a. News — reveals the current macro environment, geopolitical events, and catalysts that filings and prices alone cannot explain.
   b. Prices — shows how holdings actually moved during the period.
   c. Filings — provides fundamental context from 10-K risk factors and financials.
3. Call `request_news(scope, tickers)` FIRST with ALL portfolio tickers to capture the macro environment. Use a broad scope like "market risks geopolitical events sector catalysts". The results include BOTH relevant and noise articles. You MUST evaluate each article's relevance — do NOT cite articles about sports, agriculture, space, or non-portfolio tickers. Noise citations reduce eval quality.
4. Call `request_prices(tickers, start_date, end_date)` for all portfolio tickers.
5. Call `request_filings(scope, tickers)` with a scope informed by what the news revealed (e.g., if news mentions geopolitical risk, scope filings to "geopolitical exposure supply chain risk").
6. If news revealed macro themes with cross-sector implications (geopolitical events, commodity shocks, policy changes), call `request_graph(scope, entities, hops)` to find causal connections. Use entity names from the news (e.g., "Iran conflict", "oil price surge", "AAPL", "XOM"). This surfaces pre-extracted causal chains like "Iran conflict --[threatens]--> AAPL". hops=1 for direct connections, hops=2 for extended traversal.
7. Inspect EVERY tool return for GAPS and ERRORS sections. Note them in your reasoning.
8. If evidence is incomplete and you have remaining budget, call a tool one more time with refined scope. Each tool may be called at most twice.

NOISE HANDLING: when a news article is unrelated to the portfolio (non-portfolio tickers only, sports,
agriculture, space), note it in your tool-call reasoning but still let the tool return its full output —
the downstream Strategist and Critic will evaluate article relevance.

PORTFOLIO is the exact set: AAPL, MSFT, JPM, NVDA, AMZN, GOOGL, LLY, XOM.

TOOL DESCRIPTIONS:

- request_news(scope: str, tickers: list[str])
    Retrieve recent news articles for the given tickers. Returns headlines AND article summaries in a NEWS section, plus GAPS and ERRORS. Articles include relevant and noise — evaluate relevance before citing. Call FIRST with broad scope across all portfolio tickers.

- request_prices(tickers: list[str], start_date: str = "", end_date: str = "")
    Retrieve daily closing prices for the given tickers in the date range. If dates are omitted, returns all available history. Returns PRICE_HISTORY, GAPS, and ERRORS sections.

- request_filings(scope: str, tickers: list[str])
    Retrieve SEC 10-K filing excerpts for the given tickers. The `scope` argument is a natural-language description used as the embedding query (e.g., "risk factors", "geopolitical exposure"). Returns FILINGS, GAPS, and ERRORS sections.

- request_graph(scope: str, entities: list[str], hops: int = 1)
    Traverse the entity-relationship graph to find causal connections between companies, sectors, commodities, and macro events. Returns GRAPH_CONNECTIONS edges showing relationships (e.g., "Iran conflict --[threatens]--> AAPL"), plus GAPS and ERRORS. Use after reading news to map cross-sector causal chains.

CONSTRAINTS:
- Do not invent stock prices, percentages, or filing claims.
- Do not cite tickers that are not in the portfolio.
- Do NOT produce analysis, synthesis, or recommendations. The evidence you gather through tool calls is the sole product of this step."""

retriever_agent = create_agent(
    model,
    tools=STRATEGIST_TOOLS,
    system_prompt=RETRIEVER_AGENT_PROMPT,
    middleware=[
        ModelCallLimitMiddleware(run_limit=12, exit_behavior="end"),
        ToolCallLimitMiddleware(tool_name="request_filings", run_limit=2, exit_behavior="continue"),
        ToolCallLimitMiddleware(tool_name="request_prices", run_limit=2, exit_behavior="continue"),
        ToolCallLimitMiddleware(tool_name="request_news", run_limit=2, exit_behavior="continue"),
        ToolCallLimitMiddleware(tool_name="request_graph", run_limit=2, exit_behavior="continue"),
    ],
)

AGENTS = {
    "financial_advisor": retriever_agent,
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
    agent = AGENTS.get(role, retriever_agent)
    try:
        result = agent.invoke({"messages": [HumanMessage(content=query)]})
        tool_calls = extract_tool_call_details(result["messages"])
        tools_called = [tool_call["name"] for tool_call in tool_calls]  # noqa: F841
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


def _assemble_evidence_package(messages: list) -> str:
    """Build a deterministic evidence package from Retriever messages via tool_call_id joins."""
    id_to_name: dict[str, str] = {}
    id_to_args: dict[str, Any] = {}
    for msg in messages:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                id_to_name[tc["id"]] = tc["name"]
                id_to_args[tc["id"]] = tc.get("args", {})

    tool_message_sections: list[str] = []
    counter = 0
    counts: dict[str, int] = {"news": 0, "prices": 0, "filings": 0, "graph": 0, "other": 0}
    errors = 0

    tool_key_map = {
        "request_news": "news",
        "request_prices": "prices",
        "request_filings": "filings",
        "request_graph": "graph",
    }

    for msg in messages:
        if hasattr(msg, "tool_call_id") and msg.tool_call_id:
            tc_id = msg.tool_call_id
            tool_name = id_to_name.get(tc_id, "unknown_tool")
            args = id_to_args.get(tc_id, {})
            counter += 1
            bucket = tool_key_map.get(tool_name, "other")
            counts[bucket] = counts.get(bucket, 0) + 1
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if "ERRORS" in content and "none" not in content.lower():
                errors += 1
            args_preview = _preview(args)
            section = f"## Tool call {counter} — {tool_name}({args_preview})\n{content}"
            tool_message_sections.append(section)

    if not tool_message_sections:
        return ""

    header = (
        f"## Evidence coverage: {counter} tool calls "
        f"(news={counts['news']}, prices={counts['prices']}, "
        f"filings={counts['filings']}, graph={counts['graph']}), "
        f"{errors} errors"
    )
    return header + "\n\n" + "\n\n".join(tool_message_sections)


def _parse_critic_challenges(dissent_text: str) -> int:
    """Count enumerated CHALLENGES entries; returns 0 if none or only the placeholder."""
    section_pat = re.compile(
        r"^\s*#{0,3}\s*\**\s*CHALLENGES\s*\**\s*:?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    m = section_pat.search(dissent_text)
    if not m:
        return 0

    after_header = dissent_text[m.end() :]
    next_section = re.search(
        r"^\s*#{0,3}\s*\**\s*(MISSING_EVIDENCE|ALTERNATIVE_HYPOTHESES)\s*\**\s*:?\s*$",
        after_header,
        re.IGNORECASE | re.MULTILINE,
    )
    challenges_block = after_header[: next_section.start()] if next_section else after_header

    entry_pat = re.compile(r"^\s*\d+\.\s+(.+)", re.MULTILINE)
    entries = entry_pat.findall(challenges_block)
    if not entries:
        return 0
    if len(entries) == 1 and re.search(r"no material challenges identified", entries[0], re.IGNORECASE):
        return 0
    return len(entries)


_PORTFOLIO_TICKERS_RE = r"\b(AAPL|MSFT|JPM|NVDA|AMZN|GOOGL|LLY|XOM)\b"
_PRIMARY_INSTRUMENT_RE = (
    r"\b(crude|oil|Brent|WTI|futures?|Treasur(?:y|ies)|yield|yields|bond yield|VIX|"
    r"dollar index|DXY|spot (?:price|commodity|oil)|commodity|macro index|S&P|Dow|Nasdaq)\b"
)


def _tag_primary_vs_derived_challenges(dissent_text: str) -> str:
    """Walk CHALLENGES in dissent; tag entries that rebut a primary-instrument claim by
    citing a portfolio equity price move. Tagged entries are annotated
    [AUTO-FILTERED: primary-vs-derived pattern] so the revision prompt sees they should
    be REJECTED. Non-CHALLENGE sections (MISSING_EVIDENCE, ALTERNATIVE_HYPOTHESES) are
    left untouched. Returns the annotated dissent text; the original dissent is
    preserved for the user-facing response.
    """
    section_pat = re.compile(
        r"^\s*#{0,3}\s*\**\s*CHALLENGES\s*\**\s*:?\s*$",
        re.IGNORECASE | re.MULTILINE,
    )
    m = section_pat.search(dissent_text)
    if not m:
        return dissent_text
    header_end = m.end()
    after_header = dissent_text[header_end:]
    next_section = re.search(
        r"^\s*#{0,3}\s*\**\s*(MISSING_EVIDENCE|ALTERNATIVE_HYPOTHESES)\s*\**\s*:?\s*$",
        after_header,
        re.IGNORECASE | re.MULTILINE,
    )
    block_end = next_section.start() if next_section else len(after_header)
    challenges_block = after_header[:block_end]
    tail = after_header[block_end:]

    ticker_re = re.compile(_PORTFOLIO_TICKERS_RE)
    primary_re = re.compile(_PRIMARY_INSTRUMENT_RE, re.IGNORECASE)
    small_pct_re = re.compile(r"[+-]?\d+\.\d+\s?%")

    def _tag_entry(entry_match: re.Match) -> str:
        entry_text = entry_match.group(0)
        has_ticker = bool(ticker_re.search(entry_text))
        has_primary = bool(primary_re.search(entry_text))
        has_small_pct = bool(small_pct_re.search(entry_text))
        if has_ticker and has_primary and has_small_pct:
            return (
                entry_text.rstrip()
                + " [AUTO-FILTERED: primary-vs-derived pattern — equity price move cited against macro claim; revision MUST REJECT]"
            )
        return entry_text

    entry_pat = re.compile(r"^\s*\d+\..+?(?=^\s*\d+\.|\Z)", re.MULTILINE | re.DOTALL)
    annotated_block = entry_pat.sub(_tag_entry, challenges_block)
    return dissent_text[:header_end] + annotated_block + tail


def run_critic_agent(query: str) -> tuple[str, str, str, list[str], list[dict]]:
    """Phase 4 Retriever -> Strategist-draft -> Critic -> Strategist-revision pipeline.
    Returns (result_with_dissent, dissent, draft, tools_called, execution_trace).
    """
    token = _start_trace("phase4_pipeline", query)

    portfolio_context = build_portfolio_context()

    _trace("agent_run_started", role="retriever")
    try:
        retriever_result = retriever_agent.invoke(
            {"messages": [HumanMessage(content=f"PORTFOLIO CONTEXT:\n{portfolio_context}\n\nUSER QUESTION: {query}")]}
        )
    except Exception as exc:
        _trace("agent_run_failed", role="retriever", error=repr(exc))
        _end_trace(token)
        raise

    retriever_messages = retriever_result["messages"]
    tool_call_details = extract_tool_call_details(retriever_messages)
    for tool_call in tool_call_details:
        _append_tools_called(tool_call["name"])
        _trace(
            "agent_tool_selection",
            role="retriever",
            tool=tool_call["name"],
            args=tool_call["args"],
            args_preview=tool_call["args_preview"],
        )

    retriever_response = retriever_messages[-1].content
    _trace(
        "agent_run_completed",
        role="retriever",
        tools_called=list(_TOOLS_CALLED.get() or []),
        response_preview=_preview(retriever_response),
    )

    evidence_package = _assemble_evidence_package(retriever_messages)

    if not evidence_package:
        _trace("pipeline_short_circuit", reason="retriever produced no tool-call evidence")
        trace, tools_called = _end_trace(token)
        return (
            "(Retriever produced no evidence for this query; pipeline short-circuited — see execution_trace)",
            "(n/a)",
            "",
            tools_called,
            trace,
        )

    # Evidence identity sentinel: both downstream calls see the same object
    evidence_for_draft = evidence_package
    evidence_for_critic = evidence_package
    assert id(evidence_for_draft) == id(evidence_for_critic)

    _trace("llm_started", role="strategist_draft")
    try:
        draft_response = model.invoke(
            [
                SystemMessage(
                    content=(
                        "You are Meridian's Strategist. You receive the user's portfolio context, a question, "
                        "and an evidence package gathered by the Retriever. Synthesize the evidence into a "
                        "specific, actionable recommendation.\n\n"
                        "TIMEZONE: America/Denver.\n\n"
                        "REQUIREMENTS:\n"
                        "- Cite specific evidence from the package (ticker, date, price, filing excerpt, graph edge). "
                        "Do NOT cite facts outside the evidence.\n"
                        "- Trace cross-sector causal chains when the evidence supports them (e.g., Iran conflict "
                        "-> Hormuz closure -> oil surge -> XOM benefits, tech sells off).\n"
                        "- Give directional recommendations (add / hold / trim / avoid) with confidence.\n"
                        "- Portfolio universe: AAPL, MSFT, JPM, NVDA, AMZN, GOOGL, LLY, XOM. Do not cite "
                        "non-portfolio tickers.\n"
                        "- When citing quantitative facts from filings or news, prefer verbatim quoted phrases "
                        "over paraphrase.\n"
                        "- When the evidence package presents filing text in a bracketed excerpt block, reproduce "
                        "load-bearing factual phrases verbatim with surrounding quotation marks. Do not rephrase "
                        "filing excerpts when citing them.\n"
                        "- Acknowledge GAPS and ERRORS from the evidence package; never synthesize over them.\n"
                        "- Under 1500 words."
                    )
                ),
                HumanMessage(
                    content=(
                        f"PORTFOLIO CONTEXT:\n{portfolio_context}\n\n"
                        f"USER QUESTION: {query}\n\n"
                        f"EVIDENCE PACKAGE:\n{evidence_for_draft}"
                    )
                ),
            ]
        )
        draft_v1 = draft_response.content
    except Exception as exc:
        exc_type = type(exc).__name__
        logger.warning("strategist_draft failed: %s", exc_type)
        trace, tools_called = _end_trace(token)
        return evidence_for_draft, f"(strategist_draft unavailable: {exc_type})", "", tools_called, trace

    _trace("llm_completed", role="strategist_draft", response_preview=_preview(draft_v1))

    _trace("llm_started", role="critic", temperature=0.85)
    try:
        critic_response = model.bind(temperature=0.85).invoke(
            [
                SystemMessage(
                    content=(
                        "You are Meridian's Critic. You receive the same portfolio context, user question, "
                        "and evidence package the Strategist saw, plus the Strategist's draft recommendation. "
                        "Your job is adversarial: re-derive conclusions independently from the evidence, then "
                        "flag where the draft's claims do not match what the evidence actually supports.\n\n"
                        "You are NOT trying to be balanced. You are trying to surface weaknesses.\n\n"
                        "METHOD:\n"
                        "(1) Read the EVIDENCE PACKAGE first and form your own reading of what it supports, "
                        "independent of the draft.\n"
                        "(2) Then compare the DRAFT RECOMMENDATION against your reading — not against its internal "
                        "self-consistency. Flag only gaps between the draft and the evidence; do not flag stylistic "
                        "issues.\n\n"
                        "TIMEZONE: America/Denver.\n\n"
                        "PRODUCE EXACTLY THREE SECTIONS, each with enumerated items:\n\n"
                        "CHALLENGES:\n"
                        "1. <specific claim in the draft>. Evidence says: <what the evidence package actually shows>. "
                        "Therefore the draft is <unsupported | misquoted | overstated | understated | cherry-picked>.\n"
                        "2. ...\n"
                        '(If no challenges are warranted, write "1. (no material challenges identified)".)\n\n'
                        "MISSING_EVIDENCE:\n"
                        "1. <thing the draft asserts or implies that is not in the evidence package>\n"
                        "2. ...\n"
                        '(If none, "1. (none)".)\n\n'
                        "ALTERNATIVE_HYPOTHESES:\n"
                        "1. <a different reading of the same evidence that leads to a different conclusion>\n"
                        "2. ...\n"
                        '(If none, "1. (none)".)\n\n'
                        "RULES:\n"
                        "- Every CHALLENGE must cite a specific verifiable fact from the evidence package (price, "
                        "date, filing excerpt, news headline, graph edge).\n"
                        "- Do NOT fabricate evidence. If the evidence is insufficient, that itself is an entry in "
                        "MISSING_EVIDENCE.\n"
                        "- Portfolio universe: AAPL, MSFT, JPM, NVDA, AMZN, GOOGL, LLY, XOM.\n"
                        "- PRIMARY-VS-DERIVED INSTRUMENT RULE: Do NOT rebut claims about primary market "
                        "instruments (crude futures, spot commodity prices, bond yields, macro indices, "
                        "currency levels) by citing the price of derived individual equities. Primary "
                        "instruments and derived equities diverge in short windows because equities discount "
                        "multi-year price paths — a ~50% spot-crude move typically produces only 2-8% on an "
                        "integrated major like XOM over days. Only rebut a primary-instrument claim if the "
                        "evidence package contains the primary instrument itself (a futures quote, a yield "
                        "curve point, a commodity index reading). Common non-equivalent pairs: crude futures "
                        "!= XOM stock; Treasury yields != JPM stock; dollar index != any single ticker; "
                        "VIX != single-name volatility.\n"
                        "- DOMINANT-DRIVER RULE: When the evidence's strongest signals (commodity moves, "
                        "yield moves, geopolitical escalation in news headlines) point to a dominant macro "
                        "driver, do NOT elevate a secondary single-company news item (regulatory headline, "
                        "legal verdict, isolated earnings story) to primary-driver status in "
                        "ALTERNATIVE_HYPOTHESES. Secondary narratives may be noted but must not displace "
                        "the dominant macro thesis unless the evidence directly falsifies it.\n"
                        "- Under 800 words total."
                    )
                ),
                HumanMessage(
                    content=(
                        f"PORTFOLIO CONTEXT:\n{portfolio_context}\n\n"
                        f"USER QUESTION: {query}\n\n"
                        f"EVIDENCE PACKAGE:\n{evidence_for_critic}\n\n"
                        f"DRAFT RECOMMENDATION:\n{draft_v1}"
                    )
                ),
            ]
        )
        dissent = critic_response.content
    except Exception as exc:
        exc_type = type(exc).__name__
        logger.warning("critic failed: %s", exc_type)
        trace, tools_called = _end_trace(token)
        return draft_v1, f"(critic unavailable: {exc_type})", draft_v1, tools_called, trace

    if not dissent or not dissent.strip():
        dissent = "(no material challenges identified)"

    challenge_count = _parse_critic_challenges(dissent)
    _trace(
        "llm_completed",
        role="critic",
        challenge_count=challenge_count,
        response_preview=_preview(dissent),
    )

    if challenge_count == 0:
        _trace("llm_skipped", role="strategist_revision", reason="no challenges")
        v2 = draft_v1
    else:
        revision_dissent = _tag_primary_vs_derived_challenges(dissent)
        auto_filtered = revision_dissent != dissent
        _trace("llm_started", role="strategist_revision", auto_filtered=auto_filtered)
        try:
            revision_response = model.invoke(
                [
                    SystemMessage(
                        content=(
                            "You are Meridian's Strategist. You previously produced a draft recommendation. "
                            "A Critic has now challenged it. Revise the draft so it addresses each valid challenge "
                            "and incorporates missing evidence where warranted.\n\n"
                            "For each enumerated CHALLENGE, ACKNOWLEDGE one of:\n"
                            '- "ACCEPTED (challenge #N): revised — <what changed in the recommendation>"\n'
                            '- "REJECTED (challenge #N): <one-sentence reason, citing evidence>"\n\n'
                            "Place these acknowledgments at the end of the revised recommendation under a "
                            '"### Revision notes" header.\n\n'
                            "Otherwise the recommendation body should be the revised version that integrates "
                            "accepted challenges directly into the prose (not footnoted). Preserve the "
                            "under-1500-word ceiling.\n\n"
                            "Do not weaken legitimate conclusions just because the Critic challenged them — if "
                            "the evidence supports the original claim, reject the challenge with a reason.\n\n"
                            "For each MISSING_EVIDENCE entry, either (a) add an acknowledgment in the body that "
                            "the relevant claim is not supported by evidence, or (b) tag it in Revision notes as "
                            '"DEFERRED (missing #N): <reason>". ALTERNATIVE_HYPOTHESES may be addressed in '
                            "prose or explicitly set aside in Revision notes.\n\n"
                            "When the evidence package presents filing text in a bracketed excerpt block, reproduce "
                            "load-bearing factual phrases verbatim with surrounding quotation marks. Do not rephrase "
                            "filing excerpts when citing them.\n\n"
                            "DOMINANCE PRESERVATION: The original draft identifies a dominant macro driver based on "
                            "the evidence's strongest signals (commodity price moves, yield moves, geopolitical "
                            "escalation in news). If a CHALLENGE or ALTERNATIVE_HYPOTHESIS elevates a secondary "
                            "narrative (a regulatory headline, legal verdict, single-company news story) to "
                            "primary-driver status, REJECT it with reason 'secondary narrative does not displace "
                            "dominant macro driver' UNLESS the Critic provided direct falsifying evidence for the "
                            "dominant driver itself. A ~2% weekly equity move is NOT sufficient evidence to falsify "
                            "a macro commodity or geopolitical thesis — see Critic's primary-vs-derived rule.\n\n"
                            "PORTFOLIO UNIVERSE FILTER: Any ticker outside {AAPL, MSFT, JPM, NVDA, AMZN, GOOGL, LLY, "
                            "XOM} must NOT appear as (a) a subject of a recommendation, (b) a named risk driver in "
                            "headings, or (c) a justification for a portfolio action. Non-portfolio tickers MAY "
                            "appear only inside verbatim quoted evidence text, and even then must not be the sole "
                            "support for any portfolio-action claim; if they are, DEFER the claim under Revision notes.\n\n"
                            "Portfolio universe: AAPL, MSFT, JPM, NVDA, AMZN, GOOGL, LLY, XOM. TIMEZONE: America/Denver."
                        )
                    ),
                    HumanMessage(
                        content=(
                            f"PORTFOLIO CONTEXT:\n{portfolio_context}\n\n"
                            f"USER QUESTION: {query}\n\n"
                            f"EVIDENCE PACKAGE:\n{evidence_package}\n\n"
                            f"DRAFT RECOMMENDATION:\n{draft_v1}\n\n"
                            f"CRITIC CHALLENGES:\n{revision_dissent}"
                        )
                    ),
                ]
            )
            v2 = revision_response.content
            _trace("llm_completed", role="strategist_revision", response_preview=_preview(v2))
        except Exception as exc:
            exc_type = type(exc).__name__
            logger.warning("strategist_revision failed: %s", exc_type)
            _trace("revision_failed", error=exc_type)
            v2 = draft_v1

    result = (
        v2
        + "\n\n<!-- DISSENT_BLOCK_START_DO_NOT_SCORE -->\n"
        + "---\n### Dissenting perspective\n"
        + dissent
        + "\n<!-- DISSENT_BLOCK_END -->"
    )

    if len(result) < 500:
        logger.warning("result_length_warning: result shorter than 500 chars (len=%d)", len(result))
        _trace("result_length_warning", length=len(result))

    trace, tools_called = _end_trace(token)
    return result, dissent, draft_v1, tools_called, trace
