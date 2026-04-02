# Pipeline Implementation Plan

Transform the monolithic single-agent advisor into a 3-agent sequential pipeline: **Retriever → Strategist → Critic**.

**Rule: Do not begin a phase until the previous phase is implemented, evaluated, and its gate criteria are met.**

## Phase Status

| Phase | Stage | Status | Eval Score (avg) | Gate Met |
|-------|-------|--------|------------------|----------|
| 0 | `baseline` | **Done** | 1.0 | Yes |
| 1 | `rag_reports` | **Implemented — awaiting data** | 1.6 (partial) | No — data incomplete |
| 2 | `news_agent` | Not started | — | — |
| 3 | `graph` | Not started | — | — |
| 4 | `critic` | Not started | — | — |

Update this table as each phase is completed and evaluated.

---

## Architecture

### Communication: Plain Python orchestrator with typed data

Each agent is a LangChain `create_agent()` CompiledStateGraph. A Python orchestrator function chains them, passing structured evidence between stages. No nested graphs, no shared memory.

Only the Retriever has tools. The Strategist and Critic receive pre-gathered evidence as text, making them single-pass LLM calls (predictable cost, auditable trace).

### Evidence Package

```python
@dataclass
class EvidencePackage:
    query: str
    portfolio_context: str          # Stringified portfolio summary
    filing_excerpts: list[dict]     # [{title, text, score, lineage, file_title}]
    news_articles: list[dict]       # [{ticker, headline, body, published_at, source}]
    price_data: list[dict]          # [{symbol, price, dayChange, dayChangePct}]
    graph_connections: list[dict]   # [{source, target, relationship, evidence}]
    tools_called: list[str]         # Tool names invoked during retrieval
```

### Pipeline Flow

```
User Query
    ↓
run_pipeline(query)
    ├─ build_portfolio_context()           # serialize 8 holdings
    ├─ run_retriever(query, context)       # agent with tools → EvidencePackage
    ├─ run_strategist(query, evidence)     # no tools, pure reasoning → recommendation
    ├─ run_critic(query, evidence, rec)    # adversarial challenge → critique
    ├─ run_strategist_revision(...)        # revised rec + dissent
    └─ return {result, tools_called, critique_summary}
```

### API Contract (backward compatible)

`POST /api/agent` stays the same. Response gains optional fields:

```json
{
    "result": "...",
    "tools_called": ["get_stock_price", "query_news_articles"],
    "pipeline_stages": ["retriever", "strategist", "critic", "revision"],
    "critique_summary": "..."
}
```

Frontend reads `result` and `tools_called` — both stay in the same position. `POST /api/report-agent` unchanged.

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
| 1.1 | Pipeline orchestrator | `backend/pipeline.py` (new) | `EvidencePackage` dataclass, `build_portfolio_context()`, `run_retriever()`, `run_strategist()`, `run_pipeline()` |
| 1.2 | Retriever agent | `backend/agents.py` (modify) | New `retriever_agent` with system prompt instructing tool-based evidence gathering |
| 1.3 | Strategist agent | `backend/agents.py` (modify) | New `strategist_agent` with system prompt for evidence synthesis (no tools) |
| 1.4 | Retriever tool list | `backend/tools/tools.py` (modify) | `RETRIEVER_TOOLS = [get_stock_price, list_available_financial_reports, retrieve_embedded_financial_report_info]` |
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

#### Preliminary eval results (with partial data)

Pipeline code was evaluated on 2026-04-02 with incomplete data:

```
Stage          Ground.  Compl.  Action.  Temp.P  Rel.R   Avg    Noise  Tools
rag_reports    1.8      1.2     2.8      1.0     1.0     1.6    0      3/4
```

Temporal Precision and Relational Recall are expected to stay at 1.0 for Phase 1 — those dimensions require news (Phase 2) and graph data (Phase 3). Groundedness and Completeness should improve once all 8 filings and historical prices are available. Re-run eval after data is populated: `python script/run_eval.py --stage rag_reports --score`

### Gate: Phase 1 → Phase 2

All criteria must be met before starting Phase 2:

- [x] `backend/pipeline.py` exists and `run_pipeline()` returns `{result, tools_called}`
- [x] `/api/agent` routes through the pipeline (not the old `run_agent` path)
- [x] Retriever agent calls at least one tool in 3 of 4 preset questions
- [x] `tools_called` is non-empty in eval results
- [ ] All 8 holdings have embedded 10-K filings in `document_tree_nodes`
- [ ] Historical price data covers March 24–31, 2026 for all 8 tickers
- [ ] Eval recorded: `python script/run_eval.py --stage rag_reports --score` (with complete data)
- [ ] Groundedness avg > 1.0 (improvement over baseline)
- [ ] `noise_citation_count` = 0 for all 4 questions
- [ ] Linters pass: `ruff check` and `ruff format --check` on all modified files

---

## Phase 2: `news_agent` — Retriever gains news corpus

**Status: Not started**

**Prerequisite: Phase 1 gate met.**

**Goal**: Add a `query_news_articles` tool so the Retriever pulls temporal news from the Supabase `news_articles` table. This is the primary driver of temporal precision improvement.

### Deliverables

| # | Deliverable | File | Description |
|---|-------------|------|-------------|
| 2.1 | News query tool | `backend/tools/news_tools.py` (new) | `@tool query_news_articles(tickers, start_date, end_date, limit)` — queries Supabase |
| 2.2 | Tool registration | `backend/tools/tools.py` (modify) | Add `query_news_articles` to `RETRIEVER_TOOLS` |
| 2.3 | Retriever prompt update | `backend/agents.py` (modify) | Add step 4: use `query_news_articles` for recent news |
| 2.4 | Evidence extraction | `backend/pipeline.py` (modify) | Parse news articles from retriever tool results into `EvidencePackage.news_articles` |
| 2.5 | Eval run | — | `python script/run_eval.py --stage news_agent --score` |

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

- [ ] `backend/tools/news_tools.py` exists with working `query_news_articles` tool
- [ ] Tool registered in `RETRIEVER_TOOLS`
- [ ] Retriever calls `query_news_articles` in all 4 preset questions
- [ ] Eval recorded: `python script/run_eval.py --stage news_agent --score`
- [ ] Temporal Precision avg > 2.5 (meaningful improvement over Phase 1)
- [ ] Responses cite specific dates from March 24–31, 2026 (spot-check at least 2 questions)
- [ ] Responses mention Iran conflict, oil prices, or IRGC (spot-check at least 2 questions)
- [ ] `noise_citation_count` = 0 for all 4 questions
- [ ] Linters pass

---

## Phase 3: `graph` — Entity-relationship graph

**Status: Not started**

**Prerequisite: Phase 2 gate met.**

**Goal**: Build a static entity-relationship graph from the news corpus and give the Retriever a traversal tool for cross-sector reasoning. This is the primary driver of relational recall improvement.

### Deliverables

| # | Deliverable | File | Description |
|---|-------------|------|-------------|
| 3.1 | Entity table migration | `backend/migrations/003_entity_relationships.sql` (new) | Schema for `entity_relationships` table |
| 3.2 | Graph construction script | `script/build_graph.py` (new) | Extract entity-relationship triples from news corpus using LLM, insert into Supabase |
| 3.3 | Graph traversal tool | `backend/tools/graph_tools.py` (new) | `@tool traverse_entity_graph(entity, hops)` — queries Supabase |
| 3.4 | Tool registration | `backend/tools/tools.py` (modify) | Add `traverse_entity_graph` to `RETRIEVER_TOOLS` |
| 3.5 | Retriever prompt update | `backend/agents.py` (modify) | Add step 5: use graph tool for cross-sector connections |
| 3.6 | Strategist prompt update | `backend/agents.py` (modify) | Emphasize tracing multi-hop causal chains when graph data is present |
| 3.7 | Evidence extraction | `backend/pipeline.py` (modify) | Parse graph connections into `EvidencePackage.graph_connections` |
| 3.8 | Graph seeded | — | `python script/build_graph.py` run and data verified in Supabase |
| 3.9 | Eval run | — | `python script/run_eval.py --stage graph --score` |

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
- [ ] `backend/tools/graph_tools.py` exists with working `traverse_entity_graph` tool
- [ ] Tool registered in `RETRIEVER_TOOLS`
- [ ] Retriever calls `traverse_entity_graph` in at least 2 of 4 preset questions
- [ ] Eval recorded: `python script/run_eval.py --stage graph --score`
- [ ] Relational Recall avg > 3.0 (meaningful improvement over Phase 2)
- [ ] Responses contain at least one explicit multi-hop causal chain (spot-check 2 questions)
- [ ] `noise_citation_count` = 0 for all 4 questions
- [ ] Linters pass

---

## Phase 4: `critic` — Adversarial critic + revision loop

**Status: Not started**

**Prerequisite: Phase 3 gate met.**

**Goal**: Wire the Critic agent into the pipeline. After the Strategist produces a recommendation, the Critic challenges it, then the Strategist revises. Final output includes the revised recommendation and dissenting perspective.

### Deliverables

| # | Deliverable | File | Description |
|---|-------------|------|-------------|
| 4.1 | Critic agent prompt | `backend/agents.py` (modify) | Finalize `critic_agent` system prompt for adversarial analysis |
| 4.2 | Critic pipeline step | `backend/pipeline.py` (modify) | `run_critic(query, evidence, recommendation)` function |
| 4.3 | Revision pipeline step | `backend/pipeline.py` (modify) | `run_strategist_revision(query, evidence, recommendation, critique)` function |
| 4.4 | Pipeline wiring | `backend/pipeline.py` (modify) | `run_pipeline()` calls Retriever → Strategist → Critic → Revision |
| 4.5 | Critique in API response | `backend/pipeline.py` (modify) | Return `critique_summary` and `pipeline_stages` in pipeline output |
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
def run_pipeline(query):
    context = build_portfolio_context()
    evidence = run_retriever(query, context)
    recommendation = run_strategist(query, evidence)
    critique = run_critic(query, evidence, recommendation)
    revised = run_strategist_revision(query, evidence, recommendation, critique)
    return {
        "result": revised,
        "tools_called": evidence.tools_called,
        "critique_summary": critique,
        "pipeline_stages": ["retriever", "strategist", "critic", "revision"],
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
rag_reports    2.5      2.0     2.3      2.0     1.5     2.1
news_agent     3.5      3.5     3.0      3.8     2.5     3.3
graph          3.8      3.8     3.3      3.8     4.0     3.7
critic         4.2      4.0     3.9      4.0     4.2     4.1
```

---

## File Inventory

### New files (7)

| File | Phase |
|------|-------|
| `backend/pipeline.py` | 1 |
| `backend/tools/news_tools.py` | 2 |
| `backend/tools/graph_tools.py` | 3 |
| `backend/migrations/003_entity_relationships.sql` | 3 |
| `script/build_graph.py` | 3 |
| `backend/tests/test_pipeline.py` | 1–4 (optional) |
| `docs/11-PIPELINE-PLAN.md` | — |

### Modified files (4, across all phases)

| File | Phases |
|------|--------|
| `backend/agents.py` | 1, 2, 3, 4 |
| `backend/tools/tools.py` | 1, 2, 3 |
| `backend/app.py` | 1 |
| `backend/pipeline.py` | 2, 3, 4 |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Retriever doesn't consistently call tools | Explicit step-by-step prompt; fallback direct tool calls in orchestrator |
| Evidence package overflows context | Cap at top 5 excerpts, 10 articles, 5 graph connections; summarize |
| 4 LLM calls per query = slow | Strategist/Critic/Revision are single-pass (no loops); Retriever has max iteration cap |
| Same LLM as Strategist + Critic = weak critique | Strongly adversarial Critic prompt; consider higher temperature for Critic |
| Graph extraction from news is noisy | Manual review via `--dry-run`; pre-built static graph, not query-time |
