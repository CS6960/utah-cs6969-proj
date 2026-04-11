# Pipeline Implementation Plan

Transform the monolithic single-agent advisor into a **Strategist-orchestrated agent** that calls typed evidence tools, adding a Critic agent in Phase 4 for a two-agent adversarial loop. Phase 1 briefly shipped a sequential `Retriever → Strategist` pipeline that was clobbered by a merge and routed around in production. Phase 1b replaces that design with an LLM-driven Strategist `create_agent` loop — see `internal/phase1b_agent_pivot.md` for the full rationale.

**Rule: Do not begin a phase until the previous phase is implemented, evaluated, and its gate criteria are met.**

## Phase Status

| Phase | Stage | Status | Eval Score (avg) | Gate Met |
|-------|-------|--------|------------------|----------|
| 0 | `baseline` | **Done** | 1.0 | Yes |
| 1 | `rag_reports` | **Superseded** (sequential pipeline dead on arrival; see Phase 1b) | 1.8 | Partial |
| 1b | `strategist_agent` | **Implemented** | TBD | TBD |
| 2 | `news_agent` | Not started | — | — |
| 3 | `graph` | Not started | — | — |
| 4 | `critic` | Not started | — | — |

Update this table as each phase is completed and evaluated.

---

## Architecture

### Phase 1b onward: Strategist-orchestrated agent

The Strategist is a LangChain `create_agent()` CompiledStateGraph with three typed tools: `request_filings`, `request_prices`, `request_news`. Each tool wraps a deterministic helper (no nested LLM sub-agent) and returns an `EvidenceResponse` slice serialized as markdown. The Strategist inspects `GAPS:`/`ERRORS:` in the tool output, optionally refines its scope, and synthesizes a final answer that refuses to invent facts when the evidence is missing. Phase 4 adds a second LLM agent (the Critic) after synthesis.

Only the Strategist is an LLM-driven agent in Phase 1b. The former "Retriever agent" is realized as a **typed-adapter layer** (the three tools), not as a separate LLM sub-agent. This is an honest restatement of the "multi-agent" framing: the system becomes multi-agent in Phase 4 with the Critic.

### EvidenceResponse (typed return contract)

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

### Pipeline Flow

```
User Query
    ↓
run_strategist_agent(query)
    ├─ build_portfolio_context()           # serialize 8 holdings + cash
    ├─ strategist_agent.invoke()           # create_agent loop
    │     ├─ request_filings(scope, tickers)     # RAG excerpts
    │     ├─ request_prices(tickers, start, end) # batch price history
    │     ├─ request_news(scope, tickers)        # stub in 1b; real in Phase 2
    │     └─ synthesize final answer
    ├─ (Phase 4) run_critic(query, evidence, rec)
    ├─ (Phase 4) run_strategist_revision(...)
    └─ return {result, tools_called, execution_trace}
```

### API Contract

`POST /api/agent` calls `run_strategist_agent(query)` in Phase 1b. Response shape:

```json
{
    "result": "...",
    "tools_called": ["request_filings", "request_prices"],
    "execution_trace": [...]
}
```

Phase 4 adds `pipeline_stages` and `critique_summary` fields. Frontend reads `result` and `tools_called` — those positions stay stable. `POST /api/report-agent` is **unchanged**; it still routes through the `financial_reports_retrieval_agent` via `run_agent`.

---

## Phase 0: `baseline` — Current state

**Status: Done**

Single `financial_advisor` agent with DuckDuckGo, Yahoo Finance, stock prices, and report retrieval tools. No pipeline, no separation of retrieval and analysis.

### Eval result

| Scorer | Ground. | Compl. | Action. | Temp.P | Rel.R | Avg | Noise | Tools |
|--------|---------|--------|---------|--------|-------|-----|-------|-------|
| LLM judge | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1 (TSLA) | 0/4 |
| Human (Mikhail — finance minor, market experience) | 1 | 1 | 1 | 1 | 1 | 1.0 | — | — |

Agent failed to use its available tools across all 4 questions. Instead of querying stock prices, SEC filings, or news, it asked the user for portfolio data it already had access to. All responses were generic templates with zero grounding in the March 24–31 evaluation window.

### Gate: Phase 0 → Phase 1

- [x] Baseline eval recorded in Supabase **with all 5 dimensions** (2026-04-02)
- [x] Eval report shows scores across all 5 dimensions
- [x] Human evaluation confirms LLM judge scores (evaluator: Mikhail Berlay)
- [x] Eval framework has all 5 scoring dimensions (groundedness, completeness, actionability, temporal precision, relational recall)
- [x] Tool tracking returns actual tool names (not empty lists)
- [x] Migration 002 applied (temporal_precision, relational_recall, noise columns)

---

## Phase 1: `rag_reports` — Retriever + Strategist with SEC filings

**Status: Implemented**

**Goal**: Replace the flat advisor with a 2-agent pipeline. The Retriever gathers SEC filing evidence using tools. The Strategist synthesizes it into a recommendation. No Critic yet.

### Deliverables

| # | Deliverable | File | Description |
|---|-------------|------|-------------|
| 1.1 | Pipeline orchestrator | `backend/` (new module, since removed in Phase 1b) | `EvidencePackage` dataclass, `build_portfolio_context()`, `run_retriever()`, `run_strategist()`, `run_pipeline()` |
| 1.2 | Retriever agent | `backend/agents.py` (modify) | New `retriever_agent` with system prompt instructing tool-based evidence gathering |
| 1.3 | Strategist agent | `backend/agents.py` (modify) | New `strategist_agent` with system prompt for evidence synthesis (no tools) |
| 1.4 | Retriever tool list | `backend/agent_tools/tools.py` (modify) | `RETRIEVER_TOOLS = [get_stock_price, list_available_financial_reports, retrieve_embedded_financial_report_info]` |
| 1.5 | API wiring | `backend/app.py` (modify) | `/api/agent` calls `run_pipeline()` instead of `run_agent()` |
| 1.6 | Eval run | — | `python script/run_eval.py --stage rag_reports --score` |

### Retriever system prompt

```
You are a financial research retriever. Your job is to gather evidence, NOT to give advice.

Portfolio: {portfolio_context}

Given the user's question, systematically gather relevant data:
1. Check stock prices for relevant holdings using get_stock_price.
2. Use list_available_financial_reports to find SEC filings.
3. Use retrieve_embedded_financial_report_info for relevant excerpts.

Summarize findings in structured format:
- PRICE DATA: [list prices]
- FILING EXCERPTS: [list passages with source]
- KEY FACTS: [most important facts uncovered]

Do NOT give investment advice. Only report what the data says.
```

### Strategist system prompt

```
You are a financial strategist. You receive a user question and an evidence package
gathered by a research agent.

Synthesize the evidence into clear, actionable analysis:
1. Cross-reference sources for consistency.
2. Identify second-order effects across sectors.
3. Cite specific evidence for each claim.
4. Provide directional recommendations (add/hold/trim/avoid) with confidence.
5. Be explicit about what evidence supports vs. what is uncertain.

EVIDENCE PACKAGE:
{evidence}
```

### Data requirements

The pipeline code is implemented, but Phase 1 evaluation depends on complete data. The following must be populated before re-running the eval.

#### Historical price data (7-day window: March 24–31, 2026)

`get_stock_price` currently returns a single static snapshot from `backend/data/stock_prices.csv`. The eval ground truth references specific price movements over the week (e.g., XOM +42% YTD, consecutive selloff days on March 26–27). The retriever needs daily prices to cite changes.

**What's needed:** Daily closing prices for all 8 portfolio tickers for March 24–31, 2026 (7 trading days × 8 tickers = 56 rows). Either extend the CSV or create a Supabase table. The `get_stock_price` tool may need updating to return historical data or a new tool may be needed.

| Ticker | Status |
|--------|--------|
| AAPL | Single snapshot only |
| MSFT | Single snapshot only |
| JPM | Single snapshot only |
| NVDA | Single snapshot only |
| AMZN | Single snapshot only |
| GOOGL | Single snapshot only |
| LLY | Single snapshot only |
| XOM | Single snapshot only |

#### Financial reports (10-K filings embedded in `document_tree_nodes`)

The retriever calls `retrieve_embedded_financial_report_info` to find SEC filing excerpts. Currently only 5 of 8 holdings have embedded reports.

| Ticker | Report | Status |
|--------|--------|--------|
| AAPL | 10-K FY2025 | ✅ Embedded |
| MSFT | 10-K FY2025 | ✅ Embedded |
| JPM | 10-K FY2025 | ✅ Embedded |
| NVDA | 10-K FY2024 + FY2025 | ✅ Embedded |
| AMZN | — | ❌ **Missing — needs embedding** |
| GOOGL | — | ❌ **Missing — needs embedding** |
| LLY | — | ❌ **Missing — needs embedding** |
| XOM | — | ❌ **Missing — needs embedding** |

**What's needed:** Obtain 10-K filings for AMZN, GOOGL, LLY, and XOM, then embed and upload to the `document_tree_nodes` table using the same tree-structured embedding pipeline used for the existing reports.

#### Eval results (2026-04-03)

```
Stage          Ground.  Compl.  Action.  Temp.P  Rel.R   Avg    Noise  Tools
baseline       1.0      1.0     1.0      1.0     1.0     1.0    1      0/4
rag_reports    2.0      1.5     3.2      1.0     1.0     1.8    1      4/4
```

Temporal Precision and Relational Recall stay at 1.0 as expected — those dimensions require news (Phase 2) and graph data (Phase 3). Actionability jumped from 1.0 to 3.2 (agent now gives concrete advice grounded in portfolio data and SEC filings). One noise citation (PFE) in Q4.

### Gate: Phase 1 → Phase 2

All criteria must be met before starting Phase 2:

- [x] The Phase 1 pipeline orchestrator module existed and `run_pipeline()` returned `{result, tools_called}` (**superseded** — the module is deleted in Phase 1b; orchestration moves into `run_strategist_agent` in `backend/agents.py`)
- [~] `/api/agent` routes through the pipeline (not the old `run_agent` path) — **stale**: the multi-agent merge (`fe2d9af`) clobbered this wiring after Phase 1 shipped, so production traffic fell back to the single `financial_advisor` agent. **Phase 1b restores routing**: `/api/agent` now calls `run_strategist_agent(query)` (see Phase 1b below).
- [x] Retriever agent calls at least one tool in 3 of 4 preset questions
- [x] `tools_called` is non-empty in eval results
- [x] All 8 holdings have embedded 10-K filings in `document_tree_nodes`
- [x] Historical price data covers March 24–31, 2026 for all 8 tickers
- [x] Eval recorded: `python script/run_eval.py --stage rag_reports --score` (2026-04-03)
- [x] Groundedness avg > 1.0 (2.0 > 1.0)
- [~] `noise_citation_count` = 0 for all 4 questions — **1 noise cite (PFE) in Q4, accepted**
- [x] Linters pass: Supabase lint 0 violations

---

## Phase 1b: Strategist-Orchestrated Agent

**Status: Implemented**

**Goal**: Transform the dead Retriever→Strategist sequential pipeline into an LLM-driven Strategist agent that orchestrates evidence retrieval through three typed tools. The sequential Retriever→Strategist pipeline from Phase 1 (see `internal/phase1b_agent_pivot.md` for the full rationale) had three bugs at once: `/api/agent` did not route through `run_pipeline` after the multi-agent merge, the Retriever agent was disabled via `RETRIEVER_USE_AGENT=0` and always fell into a deterministic fallback, and the Strategist had no tools — so no LLM chose tools in any code path that served traffic. Phase 1b closes all three.

The "multi-agent" framing is honestly restated for this phase: the Strategist is the **one active LLM agent** in Phase 1b. The former Retriever is realized as a **typed-adapter layer** (three typed tools wrapping deterministic helpers), not as a separate LLM sub-agent. Phase 4 returns the system to a genuine multi-agent shape by adding a Critic for adversarial review *after* the Strategist's synthesis.

### Deliverables

| # | Deliverable | File | Description |
|---|-------------|------|-------------|
| 1b.1 | Typed tool layer | `backend/agent_tools/strategist_tools.py` (new) | `EvidenceResponse` dataclass (with `gaps`/`errors`), `FilingExcerpt`, `PriceHistoryRow`, `NewsArticle` types; `build_portfolio_context()` (cash-inclusive); `serialize_for_llm()` markdown formatter; three `@tool` wrappers `request_filings`, `request_prices`, `request_news` that call deterministic helpers and return serialized evidence slices |
| 1b.2 | Strategist agent | `backend/agents.py` (modify) | New `STRATEGIST_AGENT_PROMPT`, `strategist_agent` built via LangChain `create_agent()` with `ModelCallLimitMiddleware(run_limit=8)` and per-tool `ToolCallLimitMiddleware` instances; `run_strategist_agent(query)` entry-point; module-level `_RAG_COUNTER` `ContextVar` for defense-in-depth RAG ceiling; update `AGENTS` dict to register `strategist` |
| 1b.3 | API wiring | `backend/app.py` (modify) | `/api/agent` calls `run_strategist_agent(query)` and returns `{result, tools_called, execution_trace}`. `/api/report-agent` is **unchanged** — it still routes through `financial_reports_retrieval_agent` via `run_agent`. |
| 1b.4 | Remove dead code | `backend/` (delete Phase 1 pipeline module) | The entire sequential Phase 1 pipeline module is removed; its responsibilities move into `strategist_tools.py` (`build_portfolio_context`, serialization) and `agents.py` (`run_strategist_agent`). |
| 1b.5 | Smoke test | `script/smoke_test.py` (new) | Minimal end-to-end probe: boots the agent, runs a single canned question, asserts `tools_called` non-empty and `gaps`/`errors` surface on injected failures. |
| 1b.6 | Eval prep | `script/run_eval.py` (modify) | Drop Q5 (no longer in the March 24–31 corpus) and re-score the remaining questions under the new agent. |

### Architecture

```
User query
   ↓
run_strategist_agent(query)
   ├─ build_portfolio_context()  [holdings + cash]
   ├─ strategist_agent.invoke()  [LangChain create_agent loop]
   │     ├─ Round 1: request_filings(scope, tickers)  [→ retrieve_embedded_financial_report_info RPC]
   │     ├─ Round 2: request_prices(tickers, start, end)  [→ get_price_history_for_symbols batch]
   │     ├─ [optional] Round 3: refine scope + retry one tool
   │     └─ synthesize final answer (≤1500 words)
   └─ return (response, tools_called, execution_trace)
```

The Strategist is a top-level `create_agent` loop. It reads the user query and the cash-inclusive portfolio context, decomposes the question into evidence scopes, and calls the typed tools. Each tool wraps a deterministic helper (no nested LLM), returns an `EvidenceResponse` slice, and serializes it as a markdown block that the Strategist receives as an observation. The Strategist then inspects `GAPS:` and `ERRORS:` sections and either refines scope (one retry) or proceeds to synthesis acknowledging what's missing. It must **refuse to hallucinate around missing data** — the prompt instructs it to cite the specific gap/error rather than invent numbers.

### `EvidenceResponse` typed contract

```python
@dataclass
class EvidenceResponse:
    scope_request: str                       # echo of what Strategist asked for
    filings: list[FilingExcerpt]             # may be empty
    price_history: list[PriceHistoryRow]     # may be empty
    news: list[NewsArticle]                  # Phase 2; may be empty
    graph_connections: list[GraphEdge]       # Phase 3; may be empty
    tools_called: list[str]                  # provenance for the eval
    gaps: list[str]                          # explicit "I tried but found nothing for X"
    errors: list[str]                        # explicit "tool Y failed with Z"
```

Every tool returns an `EvidenceResponse` slice. `serialize_for_llm()` formats it with these sections, all **always present** (even when empty):

```
SCOPE: <echo>
TOOLS_CALLED: <list>
FILINGS: <excerpts | "none">
PRICE_HISTORY: <rows | "none">
GAPS: <explicit gaps | "none">
ERRORS: <explicit errors | "none">
```

The typed `EvidenceResponse` contract — specifically the `gaps` and `errors` fields — is the primary design decision that closes the Milestone 2 human-eval finding (the LLM judge could not detect infrastructure bugs like cash excluded from holdings, empty filings, or missing prices). Gaps surface empty-result tools; errors surface tool exceptions. Both land in the Strategist's context window, so the final response is **self-diagnosing** ("I could not find...") instead of silently hallucinating around missing data.

### Hard caps (cost + Supabase protection)

The agent is wrapped in LangChain middleware to enforce budgets and protect the Supabase free tier:

| Cap | Mechanism | Value |
|-----|-----------|-------|
| Total model calls per run | `ModelCallLimitMiddleware(run_limit=8)` | 8 |
| `request_filings` calls | `ToolCallLimitMiddleware(tool_name="request_filings", run_limit=2)` | 2 |
| `request_prices` calls | `ToolCallLimitMiddleware(tool_name="request_prices", run_limit=2)` | 2 |
| `request_news` calls | `ToolCallLimitMiddleware(tool_name="request_news", run_limit=1)` | 1 |
| Global RAG ceiling | `_RAG_COUNTER` `ContextVar` in `agents.py` | 3 per request |

The `_RAG_COUNTER` is defense-in-depth: even if a future tool accidentally triggers `retrieve_embedded_financial_report_info` via a code path that bypasses `ToolCallLimitMiddleware`, the ContextVar-scoped counter blocks the third call at the helper level. This directly mitigates the 2026-04-03 incident (see `docs/08-SUPABASE-FREE-TIER.md`) where a 6-way parallel fan-out triggered statement timeouts.

### Gate: Phase 1b → Phase 2

All criteria must be met before resuming Phase 2 work. These come from `internal/phase1b_agent_pivot.md` §6:

- [ ] `/api/agent` routes to `run_strategist_agent(query)` (not `run_agent` or `run_pipeline`)
- [ ] Phase 1 pipeline module deleted; no imports reference it
- [ ] `backend/agent_tools/strategist_tools.py` exports `EvidenceResponse`, `request_filings`, `request_prices`, `request_news`, `build_portfolio_context`, `serialize_for_llm`
- [ ] `build_portfolio_context` includes portfolio cash (closing the M2 human-eval bug)
- [ ] `EvidenceResponse` tool output always includes `SCOPE:`, `TOOLS_CALLED:`, `FILINGS:`, `PRICE_HISTORY:`, `GAPS:`, `ERRORS:` sections, even when empty
- [ ] `strategist_agent` is built with `ModelCallLimitMiddleware(run_limit=8)` and per-tool `ToolCallLimitMiddleware` at the documented limits
- [ ] `_RAG_COUNTER` `ContextVar` raises or returns a sentinel on the 4th RAG call within a single request
- [ ] Smoke test passes: agent calls at least one tool, returns non-empty `tools_called`, surfaces injected `gaps`/`errors` in the final response
- [ ] Eval recorded for all 4 remaining preset questions (Q5 dropped) under the new agent
- [ ] Linters pass: `ruff check`, `ruff format --check`, `python script/check_supabase_rules.py`
- [ ] CHANGELOG entry describing the pivot (Task 3.1 owns the actual edit)

### Eval expectation

Groundedness and Actionability should improve versus Phase 1 because the Strategist can now refuse to invent facts when the `gaps`/`errors` fields are populated, and because it can issue targeted scope-driven evidence requests instead of consuming a blind one-shot `EvidencePackage`. Temporal Precision and Relational Recall remain at ~1.0 — those dimensions require the news tool (Phase 2) and the entity graph (Phase 3) and Phase 1b does not add either.

---

## Phase 2: `news_agent` — Strategist gains a real news tool

**Status: Not started**

**Prerequisite: Phase 1b gate met.**

**Goal**: Replace the Phase 1b stub `request_news` tool with a real news-corpus implementation so the Strategist can pull temporal news from the Supabase `news_articles` table. This is the primary driver of temporal precision improvement.

### Deliverables

| # | Deliverable | File | Description |
|---|-------------|------|-------------|
| 2.1 | News query helper | `backend/agent_tools/news_tools.py` (new) | `query_news_articles(tickers, start_date, end_date, limit)` — queries Supabase; returns typed `NewsArticle` rows |
| 2.2 | Real `request_news` | `backend/agent_tools/strategist_tools.py` (modify) | Replace the Phase 1b stub implementation of `request_news` so it calls `query_news_articles` and populates `EvidenceResponse.news` with typed rows |
| 2.3 | Strategist prompt update | `backend/agents.py` (modify) | Update `STRATEGIST_AGENT_PROMPT` to instruct use of `request_news` for temporal corroboration; raise `ToolCallLimitMiddleware` on `request_news` from `run_limit=1` to `run_limit=2` if needed |
| 2.4 | Eval run | — | `python script/run_eval.py --stage news_agent --score` |

### Tool design

```python
@tool
def query_news_articles(
    tickers: list[str],
    start_date: str = "",
    end_date: str = "",
    limit: int = 10,
) -> str:
    """Query the news corpus for articles about specific tickers within a date range."""
```

Does NOT filter by `relevant = true`. Agent sees noise articles and must demonstrate filtering ability. Eval measures this via `noise_citation_count`.

### Gate: Phase 2 → Phase 3

All criteria must be met before starting Phase 3:

- [ ] `backend/agent_tools/news_tools.py` exists with working `query_news_articles` helper
- [ ] `request_news` in `backend/agent_tools/strategist_tools.py` is wired to the real helper (no stub) and returns populated `EvidenceResponse.news`
- [ ] Strategist calls `request_news` in all 4 preset questions
- [ ] Eval recorded: `python script/run_eval.py --stage news_agent --score`
- [ ] Temporal Precision avg > 2.5 (meaningful improvement over Phase 1b)
- [ ] Responses cite specific dates from March 24–31, 2026 (spot-check at least 2 questions)
- [ ] Responses mention Iran conflict, oil prices, or IRGC (spot-check at least 2 questions)
- [ ] `noise_citation_count` = 0 for all 4 questions
- [ ] Linters pass

---

## Phase 3: `graph` — Entity-relationship graph

**Status: Not started**

**Prerequisite: Phase 2 gate met.**

**Goal**: Build a static entity-relationship graph from the news corpus and give the Strategist a traversal tool for cross-sector reasoning. This is the primary driver of relational recall improvement.

### Deliverables

| # | Deliverable | File | Description |
|---|-------------|------|-------------|
| 3.1 | Entity table migration | `backend/supabase/migrations/003_entity_relationships.sql` (new) | Schema for `entity_relationships` table |
| 3.2 | Graph construction script | `script/build_graph.py` (new) | Extract entity-relationship triples from news corpus using LLM, insert into Supabase |
| 3.3 | Graph traversal helper | `backend/agent_tools/graph_tools.py` (new) | `traverse_entity_graph(entity, hops)` — queries Supabase; returns typed `GraphEdge` rows |
| 3.4 | `request_graph` tool | `backend/agent_tools/strategist_tools.py` (modify) | Add a fourth typed tool `request_graph(scope, entities, hops)` that wraps `traverse_entity_graph` and populates `EvidenceResponse.graph_connections`; wrap with `ToolCallLimitMiddleware(tool_name="request_graph", run_limit=2)` |
| 3.5 | Strategist prompt update | `backend/agents.py` (modify) | Update `STRATEGIST_AGENT_PROMPT` to trace multi-hop causal chains via `request_graph` when relational questions are asked |
| 3.6 | Graph seeded | — | `python script/build_graph.py` run and data verified in Supabase |
| 3.7 | Eval run | — | `python script/run_eval.py --stage graph --score` |

### Entity-relationship table

```sql
create table entity_relationships (
    id uuid primary key default gen_random_uuid(),
    source_entity text not null,
    source_type text,
    target_entity text not null,
    target_type text,
    relationship text not null,
    evidence text,
    article_id uuid references news_articles(id),
    created_at timestamptz default now()
);
```

### Graph construction

`script/build_graph.py`:
1. Load all relevant articles from `news_articles`
2. For each article, prompt LLM: extract entity-relationship triples as JSON
3. Deduplicate and insert into `entity_relationships`
4. `--dry-run` option to inspect before inserting

### Gate: Phase 3 → Phase 4

All criteria must be met before starting Phase 4:

- [ ] Migration applied: `entity_relationships` table exists in Supabase
- [ ] Graph seeded: `script/build_graph.py` run, at least 30 relationship rows in table
- [ ] `backend/agent_tools/graph_tools.py` exists with working `traverse_entity_graph` helper
- [ ] `request_graph` tool registered in `backend/agent_tools/strategist_tools.py` and wrapped with `ToolCallLimitMiddleware`
- [ ] Strategist calls `request_graph` in at least 2 of 4 preset questions
- [ ] Eval recorded: `python script/run_eval.py --stage graph --score`
- [ ] Relational Recall avg > 3.0 (meaningful improvement over Phase 2)
- [ ] Responses contain at least one explicit multi-hop causal chain (spot-check 2 questions)
- [ ] `noise_citation_count` = 0 for all 4 questions
- [ ] Linters pass

---

## Phase 4: `critic` — Adversarial critic + revision loop

**Status: Not started**

**Prerequisite: Phase 3 gate met.**

**Goal**: Add a second LLM agent — the Critic — that reviews the Strategist's synthesis adversarially, then the Strategist revises. Phase 4 is the point where the system genuinely becomes multi-agent (two LLM agents with distinct roles). The Critic runs **after** the Strategist's final synthesis; it does not participate in evidence gathering.

### Deliverables

| # | Deliverable | File | Description |
|---|-------------|------|-------------|
| 4.1 | Critic agent prompt | `backend/agents.py` (modify) | New `CRITIC_AGENT_PROMPT`; build `critic_agent` as a single-pass `create_agent()` call with no tools (receives evidence + recommendation as text) |
| 4.2 | Critic orchestration step | `backend/agents.py` (modify) | `run_critic(query, evidence, recommendation)` helper — single LLM call, returns a critique string |
| 4.3 | Revision orchestration step | `backend/agents.py` (modify) | `run_strategist_revision(query, evidence, recommendation, critique)` — re-invokes Strategist with the critique appended |
| 4.4 | Full run wiring | `backend/agents.py` (modify) | `run_strategist_agent` grows a post-synthesis branch: Strategist → Critic → Revision. Tool caps from Phase 1b still apply to the initial Strategist pass; the Critic and revision pass each count against a separate `ModelCallLimitMiddleware` budget |
| 4.5 | Critique in API response | `backend/app.py` (modify) | `/api/agent` response gains `critique_summary` and `pipeline_stages: ["strategist", "critic", "revision"]` |
| 4.6 | Eval run | — | `python script/run_eval.py --stage critic --score` |

### Critic system prompt

```
You are a financial analysis critic. Adversarially challenge the strategist's recommendation.

1. FLAG WEAK EVIDENCE: Identify claims relying on weak, stale, or insufficient evidence.
2. TEST ALTERNATIVE HYPOTHESES: For main conclusions, propose at least one plausible
   alternative interpretation. Could the data support the opposite conclusion?
3. IDENTIFY MISSING CONTEXT: Point out sectors, entities, or connections overlooked.
4. ASSESS TEMPORAL VALIDITY: Are cited facts current enough?

Be specific and constructive. Goal: strengthen the recommendation, not reject it.
```

### Revision pass

Strategist receives original recommendation + critique and produces:
1. Revised recommendation addressing valid criticism
2. Evidence chain linking each claim to source
3. Confidence assessment
4. Dissenting view (strongest counter-argument)

### Pipeline (fully wired)

```python
def run_strategist_agent(query):
    context = build_portfolio_context()
    # Phase 1b loop: Strategist orchestrates request_filings/prices/news/graph tools
    strategist_out = strategist_agent.invoke({"query": query, "portfolio": context})
    recommendation = strategist_out.final_response
    evidence = strategist_out.collected_evidence  # joined EvidenceResponse
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

### Gate: Phase 4 (final)

- [ ] Full pipeline runs: Retriever → Strategist → Critic → Revision
- [ ] Eval recorded: `python script/run_eval.py --stage critic --score`
- [ ] All 5 dimensions avg > Phase 3 avg (overall improvement)
- [ ] Actionability avg > 3.5
- [ ] Responses include dissenting perspective or explicitly acknowledge uncertainty (spot-check 2 questions)
- [ ] `noise_citation_count` = 0 for all 4 questions
- [ ] `pipeline_stages` field in API response includes all 4 stages
- [ ] Linters pass
- [ ] Full eval report shows monotonic improvement across stages: `python script/run_eval.py --report`

---

## Expected Score Progression

```
Stage          Ground.  Compl.  Action.  Temp.P  Rel.R   Avg
--------------------------------------------------------------
baseline       1.0      1.0     1.0      1.0     1.0     1.0
rag_reports    2.0      1.5     3.2      1.0     1.0     1.8
phase_1b       2.8      2.2     3.5      1.0     1.0     2.1
news_agent     3.5      3.5     3.0      3.8     2.5     3.3
graph          3.8      3.8     3.3      3.8     4.0     3.7
critic         4.2      4.0     3.9      4.0     4.2     4.1
```

Phase 1b lifts Groundedness and Actionability by wiring in LLM-driven tool selection and the `gaps`/`errors` refuse-to-hallucinate contract. Temporal Precision and Relational Recall stay flat until Phase 2 (news) and Phase 3 (graph).

---

## File Inventory

### New files (7)

| File | Phase |
|------|-------|
| `backend/agent_tools/strategist_tools.py` | 1b |
| `script/smoke_test.py` | 1b |
| `backend/agent_tools/news_tools.py` | 2 |
| `backend/agent_tools/graph_tools.py` | 3 |
| `backend/supabase/migrations/003_entity_relationships.sql` | 3 |
| `script/build_graph.py` | 3 |
| `docs/11-PIPELINE-PLAN.md` | — |

### Modified files (across all phases)

| File | Phases |
|------|--------|
| `backend/agents.py` | 1, 1b, 2, 3, 4 |
| `backend/agent_tools/tools.py` | 1, 2, 3 |
| `backend/agent_tools/strategist_tools.py` | 1b, 2, 3 |
| `backend/app.py` | 1, 1b, 4 |
| `script/run_eval.py` | 1b |

### Deleted files

| File | Phase |
|------|-------|
| `backend/pipeline.py` | 1b (superseded by `strategist_tools.py` + `run_strategist_agent`) |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Strategist doesn't call tools (same failure as Phase 0) | `STRATEGIST_AGENT_PROMPT` explicitly names `request_filings`/`request_prices`/`request_news` as required first steps; smoke test asserts non-empty `tools_called` |
| Strategist loops indefinitely on tool calls | `ModelCallLimitMiddleware(run_limit=8)` + per-tool `ToolCallLimitMiddleware` budgets enforced at the middleware layer |
| Evidence context overflows token budget | `serialize_for_llm` caps excerpts (top 5 per filing, top 10 price rows per ticker); `EvidenceResponse` tracks totals |
| Supabase RAG fan-out (2026-04-03 incident) recurs | `_RAG_COUNTER` ContextVar hard-caps RAG calls at 3 per request regardless of tool-level caps |
| Strategist hallucinates around missing data | Typed `gaps`/`errors` fields land in Strategist context; prompt instructs it to cite the gap rather than invent |
| Same LLM as Strategist + Critic = weak critique (Phase 4) | Strongly adversarial Critic prompt; consider higher temperature for Critic |
| Graph extraction from news is noisy (Phase 3) | Manual review via `--dry-run`; pre-built static graph, not query-time |
