# Agents And Tools

This document describes the backend agents, their tools, the Strategist-orchestrated architecture, and the API routes that expose them.

## Pipeline Status

| Phase | Stage | Architecture | Status |
|-------|-------|-------------|--------|
| 0 | `baseline` | Single advisor agent (monolithic) | **Done** — scored 1.0 avg (LLM + human) |
| 1 | `rag_reports` | Sequential Retriever→Strategist (doc'd, dead on arrival) | **Superseded** — see Phase 1b |
| 1b | `strategist_agent` | Strategist-orchestrated agent with typed evidence tools | **Implemented** |
| 2 | `news_agent` | Phase 1b + real `request_news` tool against the news corpus | Not started |
| 3 | `graph` | Phase 2 + `request_graph` tool for cross-sector reasoning | Not started |
| 4 | `critic` | Phase 3 + Critic LLM agent for adversarial review | Not started |

Each phase must be implemented, evaluated, and pass its gate criteria before work begins on the next phase. See `docs/11-PIPELINE-PLAN.md` for gate criteria, rationale, and deliverables; `internal/phase1b_agent_pivot.md` for the pivot memo; `docs/09-EVALUATION.md` for scoring methodology.

## Target Architecture: Strategist-Orchestrated Agent (Phase 1b)

```
User Query
    ↓
POST /api/agent
    ↓
run_strategist_agent(query)
    ├─ build_portfolio_context()        [holdings + cash]
    ├─ strategist_agent.invoke()        [LangChain create_agent loop]
    │     ├─ request_filings(scope, tickers)     → EvidenceResponse (filings)
    │     ├─ request_prices(tickers, start, end) → EvidenceResponse (price_history)
    │     ├─ request_news(scope, tickers)        → EvidenceResponse (news; stub in 1b)
    │     └─ synthesize final answer (≤1500 words)
    └─ return {result, tools_called, execution_trace}
```

The Strategist is a LangChain `create_agent()` CompiledStateGraph that holds three typed evidence tools. Each tool is a thin wrapper over a deterministic helper (no nested LLM sub-agent) and returns an `EvidenceResponse` slice serialized as markdown. The Strategist reads the observations, inspects `GAPS:` and `ERRORS:` sections, optionally refines its scope, and synthesizes a final answer.

### Honest framing of "multi-agent"

Phase 1b has **one** active LLM agent (the Strategist). The former "Retriever agent" from the sequential design is realized as a **typed-adapter layer** — three tools wrapping deterministic helpers — not as a separate LLM sub-agent. Phase 4 adds a Critic LLM agent after the Strategist's synthesis, which is when the system genuinely becomes multi-agent.

This is an honest restatement of the project's "multi-agent" framing. The Phase 1 sequential Retriever→Strategist design shipped but never routed production traffic: `/api/agent` fell back to the single `financial_advisor` agent after a merge, and the "Retriever" was a deterministic fallback (`RETRIEVER_USE_AGENT=0` by default). No LLM chose tools in any production code path until Phase 1b restored the routing via the Strategist `create_agent` loop.

### EvidenceResponse (typed return contract)

Every Strategist tool returns an `EvidenceResponse` slice, defined in `backend/agent_tools/strategist_tools.py`:

```python
@dataclass
class EvidenceResponse:
    scope_request: str                       # echo of what Strategist asked for
    filings: list[FilingExcerpt]             # may be empty
    price_history: list[PriceHistoryRow]     # may be empty
    news: list[NewsArticle]                  # Phase 2; may be empty
    graph_connections: list[GraphEdge]       # Phase 3; may be empty
    tools_called: list[str]                  # provenance for the eval
    gaps: list[str]                          # "I tried but found nothing for X"
    errors: list[str]                        # "tool Y failed with Z"
```

`serialize_for_llm()` renders this as a markdown block with **always-present** sections:

```
SCOPE: <echo>
TOOLS_CALLED: <list>
FILINGS: <excerpts or "none">
PRICE_HISTORY: <rows or "none">
GAPS: <explicit gaps or "none">
ERRORS: <explicit errors or "none">
```

The `gaps` and `errors` fields are the critical addition. They make the agent self-diagnosing: if `get_price_history_for_symbols` returns an empty set, the `gaps` field records "no price data for TICKER between START and END"; if the RPC raises, the `errors` field records the exception string. Both land in the Strategist's context window, so its final response cites the missing evidence rather than hallucinating around it. This directly closes the Milestone 2 human-eval finding that the LLM judge could not detect infrastructure bugs (cash excluded, empty filings, missing prices).

## Current State: Phase 0 (Baseline)

### Files

- [backend/agents.py](../backend/agents.py)
- [backend/agent_tools/tools.py](../backend/agent_tools/tools.py)
- [backend/agent_tools/financial_reports_tools.py](../backend/agent_tools/financial_reports_tools.py)
- [backend/app.py](../backend/app.py)
- [backend/portfolio.py](../backend/portfolio.py)

### Agent Roles

Two agent roles are currently registered:

#### `financial_advisor`

Purpose:

- Answer portfolio questions
- Discuss holdings, concentration, and performance
- Use live or cached portfolio market data when available

Behavior:

- Grounded in the user's portfolio
- Concise and analytical
- Should not invent holdings, prices, or unsupported conclusions

#### `financial_reports_embedding_specialist`

Purpose:

- Process SEC filings and other report PDFs
- Build retrieval-ready report state
- Retrieve relevant passages from embedded reports

Behavior:

- Works step by step through the report-tool workflow
- References `report_id` explicitly
- Avoids inventing report contents or retrieval output

### Tool Registry

The tool lists live in [backend/agent_tools/tools.py](../backend/agent_tools/tools.py).

#### Advisor Tools

`ADVISOR_TOOLS` currently includes:

- `DuckDuckGoSearchResults`
- `YahooFinanceNewsTool`
- `get_stock_price`
- `list_available_financial_reports`
- `retrieve_embedded_financial_report_info`

#### Report Tools

`REPORT_TOOLS` currently includes:

- `list_available_financial_reports`
- `retrieve_embedded_financial_report_info`

### Report Tool Workflow

The expected workflow for the report specialist is:

1. `list_available_financial_reports()` — discover indexed reports
2. `retrieve_embedded_financial_report_info(report_id, query, top_k=5)` — cosine search + lineage

## Phase 1b: `strategist_agent` — Strategist-Orchestrated Agent

**Status: Implemented**

Replaces the dead Phase 1 sequential pipeline with an LLM-driven Strategist that orchestrates evidence retrieval through three typed tools.

### Key files

| File | Purpose |
|------|---------|
| `backend/agent_tools/strategist_tools.py` | `EvidenceResponse` dataclass + field types, cash-inclusive `build_portfolio_context()`, `serialize_for_llm()`, three `@tool` wrappers (`request_filings`, `request_prices`, `request_news`) |
| `backend/agents.py` | `STRATEGIST_AGENT_PROMPT`, `strategist_agent` (LangChain `create_agent()` with middleware), `run_strategist_agent(query)`, `_RAG_COUNTER` `ContextVar` for defense-in-depth |
| `backend/app.py` | `/api/agent` routes to `run_strategist_agent` (see API section below) |

### Strategist tools

Each tool wraps a deterministic helper and returns a serialized `EvidenceResponse` slice. The Strategist is the only LLM in the loop.

#### `request_filings(scope, tickers)`

Wraps `retrieve_embedded_financial_report_info` (which uses the `match_document_tree_nodes` RPC). Returns SEC filing excerpts matching the scope string, filtered by the requested tickers. Populates `EvidenceResponse.filings` with `FilingExcerpt` rows (title, text, score, lineage, file_title). Populates `gaps` when the RPC returns an empty set and `errors` when it raises.

#### `request_prices(tickers, start_date, end_date)`

Wraps `get_price_history_for_symbols` — a batch query over the `stock_prices` table for the requested date window. Populates `EvidenceResponse.price_history` with `PriceHistoryRow` entries. Populates `gaps` for tickers with no rows in window and `errors` for query failures.

#### `request_news(scope, tickers)`

Phase 1b ships a **stub** that always returns an empty result with an explicit `gaps` entry ("news tool not yet implemented — Phase 2"). Phase 2 replaces the stub with a real `query_news_articles` helper against the Supabase `news_articles` table.

### Hard caps

The Strategist's `create_agent()` is wrapped with LangChain middleware to bound cost and protect the Supabase free tier:

| Cap | Mechanism | Value |
|-----|-----------|-------|
| Total model calls per run | `ModelCallLimitMiddleware(run_limit=8)` | 8 |
| `request_filings` calls | `ToolCallLimitMiddleware(tool_name="request_filings", run_limit=2)` | 2 |
| `request_prices` calls | `ToolCallLimitMiddleware(tool_name="request_prices", run_limit=2)` | 2 |
| `request_news` calls | `ToolCallLimitMiddleware(tool_name="request_news", run_limit=1)` | 1 |
| Global RAG ceiling | `_RAG_COUNTER` `ContextVar` in `backend/agents.py` | 3 per request |

`_RAG_COUNTER` is defense-in-depth: a module-level `ContextVar` that `request_filings` increments on each call and that the underlying RAG helper checks before issuing a Supabase query. If a future tool or code path bypasses `ToolCallLimitMiddleware` and accidentally issues a fourth RAG call within the same request, the counter raises and the call is refused at the helper level. This is the direct mitigation for the 2026-04-03 incident where a 6-way parallel `retrieve_embedded_financial_report_info` fan-out triggered Supabase statement timeouts (see `docs/08-SUPABASE-FREE-TIER.md`).

### New agent role

#### `strategist`

Purpose: Orchestrate typed evidence retrieval and synthesize the final answer. One active LLM agent in Phase 1b.

Tools: `request_filings`, `request_prices`, `request_news`

Behavior: Decomposes the user query into evidence scopes, calls tools, inspects `gaps`/`errors`, optionally refines scope (one retry), then synthesizes a ≤1500-word answer. Instructed to **refuse to invent facts** when gaps/errors are present.

Output: Final-answer string plus collected `tools_called` and `execution_trace` for eval.

### API changes

`POST /api/agent` calls `run_strategist_agent(query)` (replacing both `run_agent()` and the Phase 1 `run_pipeline()` that never actually routed production traffic). Response:

```json
{
  "result": "...",
  "tools_called": ["request_filings", "request_prices"],
  "execution_trace": [...]
}
```

`POST /api/report-agent` is **unchanged** — it still routes to the `financial_reports_retrieval_agent` via `run_agent`. Phase 1b only touches the Strategist path; the reports-embedding workflow is deliberately out of scope.

### Gate criteria

- `/api/agent` routes to `run_strategist_agent(query)`
- The Phase 1 pipeline module is deleted
- `backend/agent_tools/strategist_tools.py` exports `EvidenceResponse`, `request_filings`, `request_prices`, `request_news`, `build_portfolio_context`, `serialize_for_llm`
- `build_portfolio_context` includes cash
- Tool output always includes `SCOPE:`, `TOOLS_CALLED:`, `FILINGS:`, `PRICE_HISTORY:`, `GAPS:`, `ERRORS:` sections (even when empty)
- `ModelCallLimitMiddleware(run_limit=8)` + per-tool `ToolCallLimitMiddleware` active on `strategist_agent`
- `_RAG_COUNTER` raises or returns a sentinel on the 4th RAG call within a single request
- `tools_called` non-empty in 3 of 4 eval questions
- Groundedness avg > 1.0

## Phase 2: `news_agent` — Real `request_news` Tool

**Status: Not started**

**Prerequisite: Phase 1b gate met.**

Replaces the Phase 1b `request_news` stub with a real implementation against the `news_articles` Supabase table.

### Key files

| File | Purpose |
|------|---------|
| `backend/agent_tools/news_tools.py` (new) | `query_news_articles(tickers, start_date, end_date, limit)` helper; returns typed `NewsArticle` rows |
| `backend/agent_tools/strategist_tools.py` (modify) | Replace stub `request_news` with a wrapper around `query_news_articles`; populate `EvidenceResponse.news` |

### Tool design

```python
def query_news_articles(
    tickers: list[str],
    start_date: str = "",
    end_date: str = "",
    limit: int = 10,
) -> list[NewsArticle]:
```

Queries the `news_articles` Supabase table. Does NOT filter by `relevant = true` — the agent must demonstrate noise filtering ability. Eval measures this via `noise_citation_count`.

### Gate criteria

- Strategist calls `request_news` in all 4 questions
- Temporal Precision avg > 2.5
- Responses cite specific dates from March 24–31, 2026
- `noise_citation_count` = 0

## Phase 3: `graph` — Entity-Relationship Graph

**Status: Not started**

**Prerequisite: Phase 2 gate met.**

Builds a static entity-relationship graph from the news corpus and adds a fourth typed tool (`request_graph`) to the Strategist for cross-sector reasoning.

### Key files

| File | Purpose |
|------|---------|
| `backend/supabase/migrations/003_entity_relationships.sql` (new) | Entity relationships table |
| `script/build_graph.py` (new) | Extract entity-relationship triples from news corpus |
| `backend/agent_tools/graph_tools.py` (new) | `traverse_entity_graph(entity, hops)` helper returning typed `GraphEdge` rows |
| `backend/agent_tools/strategist_tools.py` (modify) | New `request_graph(scope, entities, hops)` tool that wraps the helper and populates `EvidenceResponse.graph_connections`; wrap with `ToolCallLimitMiddleware(tool_name="request_graph", run_limit=2)` |

### Graph construction

Pre-built at setup time (not query time). The script extracts entity-relationship triples from news articles using the LLM:

- Entities: companies, sectors, events, products
- Relationships: `affects`, `supplies`, `competes_with`, `benefits_from`, `threatened_by`

### Gate criteria

- Graph seeded with 30+ relationship rows
- Strategist calls `request_graph` in 2+ of 4 questions
- Relational Recall avg > 3.0
- Responses contain explicit multi-hop causal chains

## Phase 4: `critic` — Adversarial Critic + Revision

**Status: Not started**

**Prerequisite: Phase 3 gate met.**

Adds a second LLM agent — the Critic — that runs **after** the Strategist's synthesis to challenge it adversarially, after which the Strategist revises. This is the point where the system becomes genuinely multi-agent: two LLM agents (Strategist + Critic) with distinct roles.

### New agent role

#### `critic`

Purpose: Adversarially challenge the Strategist's recommendation.

Tools: None — receives evidence + recommendation as text.

Responsibilities:
1. Flag weak or stale evidence
2. Test alternative hypotheses
3. Identify missing relational context
4. Assess temporal validity

### Pipeline (fully wired)

```python
def run_strategist_agent(query):
    context = build_portfolio_context()
    strategist_out = strategist_agent.invoke({"query": query, "portfolio": context})
    recommendation = strategist_out.final_response
    evidence = strategist_out.collected_evidence
    # Phase 4 addition: Critic reviews + Strategist revises
    critique = run_critic(query, evidence, recommendation)
    revised = run_strategist_revision(query, evidence, recommendation, critique)
    return {
        "result": revised,
        "tools_called": evidence.tools_called,
        "critique_summary": critique,
        "pipeline_stages": ["strategist", "critic", "revision"],
    }
```

### Gate criteria (final)

- Full run: Strategist (with tools) → Critic → Revision
- All 5 dimensions avg > Phase 3 avg
- Actionability avg > 3.5
- Responses include dissenting perspective
- Full eval report shows monotonic improvement across all stages

## API Endpoints

The FastAPI entry points are defined in [backend/app.py](../backend/app.py).

### `POST /api/agent`

General-purpose agent endpoint. In Phase 1b it calls `run_strategist_agent(query)` directly; the sequential pipeline path from Phase 1 is deleted.

Request body:

```json
{
  "query": "What is my portfolio concentration risk?",
  "role": "financial_advisor"
}
```

Response:

```json
{
  "result": "...",
  "tools_called": ["request_filings", "request_prices"],
  "execution_trace": [...]
}
```

Phase 4 adds `pipeline_stages` and `critique_summary` fields.

### `POST /api/report-agent`

Dedicated report-agent endpoint. **Unchanged by Phase 1b.** Still routes to `financial_reports_retrieval_agent` via `run_agent`.

Request body:

```json
{
  "query": "Download NVIDIA's 10-K, embed it, and retrieve the risk factors section."
}
```

This always routes to `financial_reports_retrieval_agent` (the dedicated report-embedding workflow).

## Portfolio Dependency

The advisor-facing portfolio context comes from [backend/portfolio.py](../backend/portfolio.py), which keeps:

- The static portfolio membership (8 holdings)
- The latest retrieved market snapshot
- Helper accessors for portfolio-wide and per-symbol reads

## Operational Notes

- The report tools currently use Supabase for persistent vector storage.
- TOC detection and section-map generation still rely on structured JSON responses.
- Section content generation relies on plain text responses for embedding.
- The Strategist-orchestrated agent layer lives in `backend/agent_tools/strategist_tools.py` (tools, typed contract, serialization) and `backend/agents.py` (`strategist_agent`, `run_strategist_agent`). Phases 2 and 3 add new tools to `strategist_tools.py`; Phase 4 adds a Critic agent in `agents.py` that runs after the Strategist's synthesis.
