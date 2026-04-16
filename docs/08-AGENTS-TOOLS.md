# Agents And Tools

This document describes the backend agents, their tools, the Strategist-orchestrated architecture, and the API routes that expose them.

## Pipeline Status

| Phase | Stage | Architecture | Status |
|-------|-------|-------------|--------|
| 0 | `baseline` | Single advisor agent (monolithic) | **Done** — scored 1.0 avg (LLM + human) |
| 1 | `rag_reports` | Sequential Retriever→Strategist (doc'd, dead on arrival) | **Superseded** — see Phase 1b |
| 1b | `strategist_agent` | Strategist-orchestrated agent with typed evidence tools | **Implemented** |
| 2 | `news_agent` | Phase 1b + real `request_news` tool against the news corpus | **Implemented** |
| 3 | `graph` | Phase 2 + `request_graph` tool for cross-sector reasoning | **Implemented** |
| 4 | `critic` | Phase 3 + grounded Critic pipeline (Retriever → evidence assembly → Strategist-draft → Critic → Strategist-revision) | **Implemented** |

Each phase must be implemented, evaluated, and pass its gate criteria before work begins on the next phase. See `docs/11-PIPELINE-PLAN.md` for gate criteria, rationale, and deliverables; `internal/phase1b_agent_pivot.md` for the pivot memo; `docs/09-EVALUATION.md` for scoring methodology.

## Final Design (post-Phase 4, 2026-04-16)

This section is the authoritative snapshot of the current production design. Per-phase sections below are preserved as the evolution narrative.

### Pipeline (one invocation of `POST /api/agent`)

```
User Query
    │
    ▼
run_critic_agent(query)                               [backend/agents.py]
    │
    ├─ build_portfolio_context()                      [backend/agent_tools/strategist_tools.py]
    │     ├─ get_live_portfolio()                     → holdings, cashBalances, latestTradingDate
    │     └─ get_portfolio_weights()                  → per-position $ / %NAV / %equity, sorted desc
    │         └─ renders POSITION WEIGHTS block + CONCENTRATION FRAMING directive
    │
    ├─ retriever_agent.invoke()                       [LangChain create_agent, 4 typed tools]
    │     ├─ request_news(scope, tickers)             → NEWS section in EvidenceResponse
    │     ├─ request_prices(tickers, start, end)      → PRICE_HISTORY section
    │     ├─ request_filings(scope, tickers)          → FILINGS section (RAG cap: 3/request)
    │     └─ request_graph(scope, entities, hops)     → GRAPH_CONNECTIONS section
    │     (middleware: 12 total model calls, 2 calls per tool)
    │
    ├─ _assemble_evidence_package(messages)           [deterministic, tool_call_id joins]
    │     → numbered "## Tool call N — name(args)" blocks + coverage header
    │     → empty result triggers pipeline_short_circuit; rest of pipeline skipped
    │
    ├─ Strategist draft  (model.invoke, tool-free, ≤1500 words)
    │     Sees: portfolio_context (with weights), query, evidence_package
    │     Rules: evidence-only citations, verbatim filing quotes, cost-basis-aware trims,
    │            portfolio universe filter
    │     → draft_v1
    │
    ├─ Critic  (model.bind(temperature=0.85).invoke, tool-free, ≤800 words)
    │     Sees: portfolio_context, query, evidence_package, draft_v1
    │     Output: CHALLENGES / MISSING_EVIDENCE / ALTERNATIVE_HYPOTHESES
    │     Rules: primary-vs-derived (don't rebut macro with equity %), dominant-driver
    │     → dissent;  _parse_critic_challenges(dissent) counts enumerated entries
    │     → 0 challenges → skip revision, return draft_v1 as v2
    │
    ├─ _tag_primary_vs_derived_challenges(dissent)    [code pre-filter]
    │     Annotates CHALLENGES entries that rebut a primary-instrument claim by citing
    │     a portfolio equity % move with "[AUTO-FILTERED: ... revision MUST REJECT]"
    │     Original dissent preserved for user-facing response.
    │
    └─ Strategist revision  (model.invoke, tool-free, ≤1500 words)
          Sees: portfolio_context, query, evidence_package, draft_v1, annotated dissent
          Rules: dominance preservation, portfolio universe filter, cost-basis-aware trims,
                 ACCEPTED/REJECTED per CHALLENGE, DEFERRED per MISSING_EVIDENCE
          → v2;  result = v2 + "<!-- DISSENT_BLOCK_START_DO_NOT_SCORE -->\n---\n### Dissenting perspective\n"
                          + dissent + "\n<!-- DISSENT_BLOCK_END -->"

Response: {result, dissent, draft, tools_called, execution_trace}
```

### Portfolio context (always visible to all four LLM stages)

`build_portfolio_context()` renders one string that is injected into the Retriever HumanMessage, the Strategist-draft HumanMessage, the Critic HumanMessage, and the Strategist-revision HumanMessage. It contains:

- **PORTFOLIO HOLDINGS** — per-symbol: name, shares (4 dp), current price, avgCost, day change
- **CASH BALANCES** — per-currency cash amounts
- **LATEST TRADING DATE** — ISO date of the latest close
- **POSITION WEIGHTS** — per-symbol `$ marketValue`, `% of NAV`, `% of equity`, sorted desc; equity/cash split; total NAV
- **CONCENTRATION FRAMING** — a one-line directive instructing the model to express concentration in % of NAV (never "X of 8 holdings")

The weight block is computed by `get_portfolio_weights()` in `backend/portfolio.py`. Weights are fresh per request (no cache) and include a fallback: if the computation raises, the weight block is omitted and the rest of the context is still rendered.

### Strategist / Critic prompt guardrails

Rules encoded in the prompts that govern recommendation quality:

| Rule | Where | Purpose |
|------|-------|---------|
| **Evidence-only citations** | draft, revision | No facts outside `EVIDENCE PACKAGE`; verbatim quotes for filing excerpts |
| **Portfolio universe filter** | draft, revision | Non-portfolio tickers (e.g. META, TSLA) may appear only inside verbatim quotes, never as action subjects |
| **Cost-basis-aware trims** | draft, revision | Trim / de-risk / profit-take actions must cite per-position `shares * (price - avgCost)` and propose tight stops near breakeven for positions close to cost; blanket sector-weight targets are rejected |
| **Concentration framing** | portfolio context directive | Concentration expressed in % of NAV, never position count |
| **Primary-vs-derived instrument** | Critic, code pre-filter | Critic cannot rebut primary-instrument claims (crude futures, yields, macro indices) by citing derived equity % moves; violations are auto-tagged for revision REJECT |
| **Dominant-driver** | Critic, revision (DOMINANCE PRESERVATION) | Secondary narratives (regulatory headlines, legal verdicts, single-company news) do not displace the dominant macro driver in ALTERNATIVE_HYPOTHESES unless the Critic directly falsifies the dominant driver |
| **Acknowledge GAPS/ERRORS** | draft | Never synthesize over missing evidence; cite the `GAPS` or `ERRORS` line instead |

### Dissent block delimiter

The final `result` string embeds the Critic's dissent under an HTML-comment delimiter:

```html
<!-- DISSENT_BLOCK_START_DO_NOT_SCORE -->
---
### Dissenting perspective
<dissent text>
<!-- DISSENT_BLOCK_END -->
```

The delimiter is machine-strippable. `script/run_eval.py` strips it via `_strip_dissent_block()` before sending the response to the LLM judge so the judge scores only the revised recommendation (v2), not v2+dissent. The frontend displays the full block as-is.

### Data sources

| Source | Table / API | Window |
|--------|-------------|--------|
| Holdings | `portfolio_positions` (shares, avg_cost) | live |
| Cash | `portfolio_cash` (currency, cash_balance) | live |
| Stock prices | `stock_prices` (close) | 2026-03-24 → 2026-04-02 (8 trading days, 8 tickers) |
| News | `news_articles` | 2026-03-13 → 2026-04-02 (90 articles, includes noise) |
| Filings | `document_tree_nodes` + `match_document_tree_nodes` RPC | 10-K FY2025 for each of 8 tickers |
| Graph | `entity_relationships` (source, relationship, target, evidence) | ~162 edges pre-extracted from news corpus |

Portfolio universe is fixed: **AAPL, MSFT, JPM, NVDA, AMZN, GOOGL, LLY, XOM**.

## Target Architecture: Three-Role Grounded Critic Pipeline (Phase 4)

```
User Query
    ↓
POST /api/agent
    ↓
run_critic_agent(query)                      [bypasses AGENTS dict]
    ├─ build_portfolio_context()             [holdings + cash]
    ├─ retriever_agent.invoke()              [LangChain create_agent loop — 4 tools]
    │     ├─ request_news(scope, tickers)    → EvidenceResponse (news)
    │     ├─ request_prices(tickers, ...)    → EvidenceResponse (price_history)
    │     ├─ request_filings(scope, tickers) → EvidenceResponse (filings)
    │     └─ request_graph(scope, entities, hops) → EvidenceResponse (graph)
    ├─ _assemble_evidence_package(messages)  [deterministic; tool_call_id joins]
    │     → numbered sections per ToolMessage; empty → pipeline_short_circuit
    ├─ model.invoke()  [Strategist-draft — tool-free LLM call]
    │     → draft_v1 (≤1500 words, cites evidence verbatim)
    ├─ model.bind(temperature=0.85).invoke()  [Critic — tool-free LLM call]
    │     → dissent (CHALLENGES / MISSING_EVIDENCE / ALTERNATIVE_HYPOTHESES)
    │     → parsed by _parse_critic_challenges(); 0 challenges → skip revision
    └─ model.invoke()  [Strategist-revision — tool-free LLM call, skip if 0 challenges]
          → v2 + "---\n### Dissenting perspective\n" + dissent
          → return (result, dissent, draft_v1, tools_called, execution_trace)
```

The Retriever is the only LangChain `create_agent()` loop in the pipeline. It calls four typed tools (`request_news`, `request_prices`, `request_filings`, `request_graph`) and its final AIMessage is discarded after evidence assembly. The three downstream calls (Strategist-draft, Critic, Strategist-revision) are direct `model.invoke()` calls with no tools, making the pipeline fully deterministic after the Retriever's tool loop completes.

`/api/agent` calls `run_critic_agent` directly. The `AGENTS` dict is retained but only reached by `run_agent()`, which is used exclusively by `/api/report-agent` (`financial_reports_retrieval_agent` role).

### Honest framing of "multi-agent"

Phase 4 has **three** active LLM roles: Retriever (tool-loop), Critic (adversarial, tool-free), and Strategist (draft + revision, tool-free). The Retriever and Critic are distinct agents with conflicting objectives; the Strategist-revision role incorporates or rebuts Critic challenges with evidence citations. This is the first phase where the system is genuinely multi-agent by any reasonable definition.

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

## Archived: Phase 0 (Baseline)

> **Historical note.** The sections below describe the pre-pipeline Phase 0 architecture. These tools (`ADVISOR_TOOLS`, `REPORT_TOOLS`, `DuckDuckGoSearchResults`, `YahooFinanceNewsTool`, `get_stock_price`, `get_portfolio_holdings`, `get_stock_price_history`, `calculator` — helpers only; `calculator` is retained inside `REPORT_RETRIEVAL_TOOLS`) were removed during the Phase 1b and Phase 4 refactors. `/api/agent` now runs the Phase 4 three-role pipeline described above; `/api/report-agent` runs `financial_reports_retrieval_agent` over `REPORT_RETRIEVAL_TOOLS`. This section is preserved for historical context only.

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
| `backend/agent_tools/strategist_tools.py` | `EvidenceResponse` dataclass + field types, cash-inclusive `build_portfolio_context()`, `serialize_for_llm()`, four `@tool` wrappers (`request_filings`, `request_prices`, `request_news`, `request_graph`) |
| `backend/agents.py` | `RETRIEVER_AGENT_PROMPT`, `retriever_agent` (LangChain `create_agent()` with middleware), `run_critic_agent(query)`, `_assemble_evidence_package`, `_parse_critic_challenges`, `_RAG_COUNTER` `ContextVar` for defense-in-depth |
| `backend/app.py` | `/api/agent` routes to `run_critic_agent` directly; `/api/report-agent` unchanged (routes via `run_agent` to `financial_reports_retrieval_agent`) |

### Strategist tools

Each tool wraps a deterministic helper and returns a serialized `EvidenceResponse` slice. The Strategist is the only LLM in the loop.

#### `request_filings(scope, tickers)`

Wraps `retrieve_embedded_financial_report_info` (which uses the `match_document_tree_nodes` RPC). Returns SEC filing excerpts matching the scope string, filtered by the requested tickers. Populates `EvidenceResponse.filings` with `FilingExcerpt` rows (title, text, score, lineage, file_title). Populates `gaps` when the RPC returns an empty set and `errors` when it raises.

#### `request_prices(tickers, start_date, end_date)`

Wraps `get_price_history_for_symbols` — a batch query over the `stock_prices` table for the requested date window. Populates `EvidenceResponse.price_history` with `PriceHistoryRow` entries. Populates `gaps` for tickers with no rows in window and `errors` for query failures.

#### `request_news(scope, tickers)`

Phase 1b ships a **stub** that always returns an empty result with an explicit `gaps` entry ("news tool not yet implemented — Phase 2"). Phase 2 replaces the stub with a real `query_news_articles` helper against the Supabase `news_articles` table.

### Hard caps

The Retriever's `create_agent()` is wrapped with LangChain middleware to bound cost and protect the Supabase free tier:

| Cap | Mechanism | Value |
|-----|-----------|-------|
| Total model calls per run | `ModelCallLimitMiddleware(run_limit=12)` | 12 |
| `request_filings` calls | `ToolCallLimitMiddleware(tool_name="request_filings", run_limit=2)` | 2 |
| `request_prices` calls | `ToolCallLimitMiddleware(tool_name="request_prices", run_limit=2)` | 2 |
| `request_news` calls | `ToolCallLimitMiddleware(tool_name="request_news", run_limit=2)` | 2 |
| `request_graph` calls | `ToolCallLimitMiddleware(tool_name="request_graph", run_limit=2)` | 2 |
| Global RAG ceiling | `_RAG_COUNTER` `ContextVar` in `backend/agents.py` | 3 per request |

`_RAG_COUNTER` is defense-in-depth: a module-level `ContextVar` that `request_filings` increments on each call and that the underlying RAG helper checks before issuing a Supabase query. If a future tool or code path bypasses `ToolCallLimitMiddleware` and accidentally issues a fourth RAG call within the same request, the counter raises and the call is refused at the helper level. This is the direct mitigation for the 2026-04-03 incident where a 6-way parallel `retrieve_embedded_financial_report_info` fan-out triggered Supabase statement timeouts (see `docs/08-SUPABASE-FREE-TIER.md`).

### Active agent roles (Phase 4)

#### `retriever` (via `retriever_agent`)

Purpose: Gather evidence with four typed tools. Produces no analysis or recommendations.

Tools: `request_news`, `request_prices`, `request_filings`, `request_graph`

Behavior: Decomposes the user query into evidence needs, calls tools in the prescribed order (news first, then prices, then filings, then graph if cross-sector causal chains are indicated). Final AIMessage is discarded after `_assemble_evidence_package` processes the ToolMessages.

#### `strategist` (Strategist-draft and Strategist-revision, tool-free)

Purpose: Synthesize the evidence package into a specific, actionable recommendation (draft), then revise it in response to Critic challenges.

Tools: None — direct `model.invoke()` calls.

Behavior: Draft cites evidence verbatim (price, date, filing excerpt, graph edge). Revision acknowledges each CHALLENGE as ACCEPTED or REJECTED with evidence citation.

#### `critic` (tool-free, `temperature=0.85`)

Purpose: Adversarially re-derive conclusions from the same evidence package and flag where the Strategist-draft's claims do not match what the evidence actually supports.

Tools: None — direct `model.bind(temperature=0.85).invoke()` call.

Output: Three structured sections: CHALLENGES (enumerated), MISSING_EVIDENCE, ALTERNATIVE_HYPOTHESES. Parsed by `_parse_critic_challenges`; 0 challenges triggers revision skip.

### API changes

`POST /api/agent` calls `run_critic_agent(query)` directly, bypassing the `AGENTS` dict. Phase 4 response:

```json
{
  "result": "<revised recommendation>---\n### Dissenting perspective\n<critic output>",
  "dissent": "<critic output>",
  "draft": "<strategist draft before revision>",
  "tools_called": ["request_news", "request_filings", "request_prices", "request_graph"],
  "execution_trace": [...]
}
```

`result` embeds the Critic's output under a `### Dissenting perspective` header (separated by `---`) for backwards-compatible single-string consumers. Programmatic consumers can read the `dissent` key directly or split `result` on `---`.

`POST /api/report-agent` is **unchanged** — still routes to `financial_reports_retrieval_agent` via `run_agent`. The Phase 4 changes do not touch the reports-embedding workflow.

### Gate criteria (Phase 1b — historical, superseded by Phase 4)

> **Historical note.** Phase 1b gate was met 2026-04-11; Phase 4 then renamed `strategist_agent` → `retriever_agent`, replaced `run_strategist_agent` with `run_critic_agent`, and raised `ModelCallLimitMiddleware(run_limit=12)` to accommodate the 4th tool (`request_graph`). The criteria below describe Phase 1b at the time it shipped; they remain satisfied under Phase 4 except where explicitly superseded.

- `/api/agent` routes to the Phase-4 `run_critic_agent(query)` (was: `run_strategist_agent`)
- The Phase 1 pipeline module is deleted
- `backend/agent_tools/strategist_tools.py` exports `EvidenceResponse`, `request_filings`, `request_prices`, `request_news`, `request_graph`, `build_portfolio_context`, `serialize_for_llm`
- `build_portfolio_context` includes cash
- Tool output always includes `SCOPE:`, `TOOLS_CALLED:`, `FILINGS:`, `PRICE_HISTORY:`, `NEWS:`, `GRAPH_CONNECTIONS:`, `GAPS:`, `ERRORS:` sections (even when empty)
- `ModelCallLimitMiddleware(run_limit=12)` + per-tool `ToolCallLimitMiddleware(run_limit=2)` active on `retriever_agent` (was: `strategist_agent`, run_limit=8)
- `_RAG_COUNTER` raises or returns a sentinel on the 4th RAG call within a single request
- `tools_called` non-empty in 3 of 4 eval questions
- Groundedness avg > 1.0

## Phase 2: `news_agent` — Real `request_news` Tool

**Status: Implemented**

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

**Status: Implemented**

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

## Phase 4: `critic` — Grounded Adversarial Critic + Revision

**Status: Implemented**

**Prerequisite: Phase 3 gate met.**

Adds two additional tool-free LLM roles — Critic and Strategist-revision — after the Retriever's evidence assembly. The Retriever is renamed from `strategist_agent` and restricted to evidence gathering only; synthesis is moved downstream. This is the first phase where the system is genuinely multi-agent.

### Key files

| File | Purpose |
|------|---------|
| `backend/agents.py` | `RETRIEVER_AGENT_PROMPT`, `retriever_agent`, `run_critic_agent(query)`, `_assemble_evidence_package(messages)`, `_parse_critic_challenges(dissent_text)` |
| `backend/app.py` | `/api/agent` calls `run_critic_agent` directly (bypasses `AGENTS` dict) |
| `script/smoke_test.py` | `run_m_critic()` milestone asserting `dissent`, `draft`, and `### Dissenting perspective` presence; gated behind `--include-critic` |

### Evidence assembly

`_assemble_evidence_package(messages)` iterates the Retriever's full message list, joins `ToolMessage` content to the originating tool call via `tool_call_id`, and renders numbered `## Tool call N — <name>(<args>)` sections with an evidence-coverage header. If no ToolMessages are found, returns an empty string, triggering the `pipeline_short_circuit` event and early return.

### Critic output format

The Critic is instructed to produce exactly three sections with enumerated items:

```
CHALLENGES:
1. <draft claim>. Evidence says: <what evidence shows>. Therefore draft is <verdict>.

MISSING_EVIDENCE:
1. <claim implied but not in evidence>

ALTERNATIVE_HYPOTHESES:
1. <alternative reading of the same evidence>
```

`_parse_critic_challenges` counts enumerated CHALLENGES entries. If 0 (or only the "no material challenges identified" placeholder), Strategist-revision is skipped and `draft_v1` is returned unchanged.

### Gate criteria (final)

- `run_critic_agent` wired as the sole handler for `POST /api/agent`
- `data.dissent` non-empty (≥200 chars) in smoke test
- `### Dissenting perspective` header present in `data.result`
- `data.draft` returned as a string
- All 5 eval dimensions avg > Phase 3 avg
- Responses include dissenting perspective

## API Endpoints

The FastAPI entry points are defined in [backend/app.py](../backend/app.py).

### `POST /api/agent`

General-purpose agent endpoint. In Phase 4 it calls `run_critic_agent(query)` directly, bypassing the `AGENTS` dict. The `role` field in the request body is ignored for this endpoint.

Request body:

```json
{
  "query": "What is my portfolio concentration risk?"
}
```

Response:

```json
{
  "result": "<revised recommendation>\n\n---\n### Dissenting perspective\n<critic output>",
  "dissent": "<critic output>",
  "draft": "<strategist draft before revision>",
  "tools_called": ["request_news", "request_prices", "request_filings", "traverse_entity_graph"],
  "execution_trace": [...]
}
```

All timestamps in `execution_trace` events use Denver time (`America/Denver`).

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
- The Phase 4 pipeline lives in `backend/agents.py` (`retriever_agent`, `run_critic_agent`, `_assemble_evidence_package`, `_parse_critic_challenges`) and `backend/agent_tools/strategist_tools.py` (typed tools, `EvidenceResponse`, `serialize_for_llm`, `build_portfolio_context`). The `financial_reports_retrieval_agent` and `REPORT_RETRIEVAL_TOOLS` are unchanged and serve only `/api/report-agent`.
