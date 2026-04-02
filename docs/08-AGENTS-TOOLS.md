# Agents And Tools

This document describes the backend agents, their tools, the pipeline architecture, and the API routes that expose them.

## Pipeline Status

| Phase | Stage | Architecture | Status |
|-------|-------|-------------|--------|
| 0 | `baseline` | Single advisor agent (monolithic) | **Done** — scored 1.0 avg (LLM + human) |
| 1 | `rag_reports` | Retriever + Strategist with SEC filings | Not started |
| 2 | `news_agent` | + News corpus tool for temporal awareness | Not started |
| 3 | `graph` | + Entity-relationship graph for cross-sector reasoning | Not started |
| 4 | `critic` | + Adversarial critic agent with revision loop | Not started |

Each phase must be implemented, evaluated, and pass its gate criteria before work begins on the next phase. See `docs/11-PIPELINE-PLAN.md` for gate criteria and `docs/09-EVALUATION.md` for scoring methodology.

## Target Architecture: 3-Agent Pipeline

```
User Query
    ↓
POST /api/agent
    ↓
run_pipeline(query)
    ├─ build_portfolio_context()
    ├─ Retriever Agent  (tools: prices, filings, news, graph)  → EvidencePackage
    ├─ Strategist Agent (no tools, evidence in prompt)          → Recommendation
    ├─ Critic Agent     (no tools, evidence + rec in prompt)    → Critique
    ├─ Strategist Revision (evidence + rec + critique)          → Final answer
    └─ return {result, tools_called, pipeline_stages, critique_summary}
```

Only the Retriever has tools. Strategist and Critic are single-pass LLM calls receiving pre-gathered evidence as text. This keeps costs predictable and reasoning traces auditable.

### Evidence Package

The Retriever's output is a structured `EvidencePackage` containing:

- `filing_excerpts` — SEC filing passages from tree-RAG (Phase 1+)
- `news_articles` — temporal news from `news_articles` table (Phase 2+)
- `price_data` — current stock prices (Phase 1+)
- `graph_connections` — cross-sector entity relationships (Phase 3+)
- `tools_called` — which tools the Retriever invoked

The Strategist and Critic receive this as formatted text in their prompt.

## Current State: Phase 0 (Baseline)

### Files

- [backend/agents.py](../backend/agents.py)
- [backend/tools/tools.py](../backend/tools/tools.py)
- [backend/tools/financial_reports_tools.py](../backend/tools/financial_reports_tools.py)
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

The tool lists live in [backend/tools/tools.py](../backend/tools/tools.py).

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

## Phase 1: `rag_reports` — Retriever + Strategist

**Status: Not started**

Replaces the flat advisor with a 2-stage pipeline. The Retriever gathers SEC filing evidence using tools. The Strategist synthesizes it into a recommendation.

### New files

| File | Purpose |
|------|---------|
| `backend/pipeline.py` | Orchestrator: `EvidencePackage`, `build_portfolio_context()`, `run_retriever()`, `run_strategist()`, `run_pipeline()` |

### New agent roles

#### `retriever`

Purpose: Gather evidence from available tools. Does NOT give advice.

Tools: `get_stock_price`, `list_available_financial_reports`, `retrieve_embedded_financial_report_info`

Output: Structured evidence summary (price data, filing excerpts, key facts).

#### `strategist`

Purpose: Synthesize evidence into actionable financial analysis.

Tools: None — receives evidence as text in its prompt.

Output: Directional recommendations with confidence levels, citing specific evidence.

### API changes

`POST /api/agent` calls `run_pipeline()` instead of `run_agent()`. Response gains optional `pipeline_stages` field. Backward compatible.

### Gate criteria

- `tools_called` non-empty in 3 of 4 eval questions
- Groundedness avg > 1.0
- Eval recorded for `rag_reports` stage

## Phase 2: `news_agent` — News Corpus Tool

**Status: Not started**

**Prerequisite: Phase 1 gate met.**

Adds a `query_news_articles` tool to the Retriever so it can pull temporal news from the `news_articles` Supabase table.

### New files

| File | Purpose |
|------|---------|
| `backend/tools/news_tools.py` | `@tool query_news_articles(tickers, start_date, end_date, limit)` |

### Tool design

```python
@tool
def query_news_articles(
    tickers: list[str],
    start_date: str = "",
    end_date: str = "",
    limit: int = 10,
) -> str:
```

Queries the `news_articles` Supabase table. Does NOT filter by `relevant = true` — the agent must demonstrate noise filtering ability.

### Gate criteria

- Retriever calls `query_news_articles` in all 4 questions
- Temporal Precision avg > 2.5
- Responses cite specific dates from March 24–31, 2026
- `noise_citation_count` = 0

## Phase 3: `graph` — Entity-Relationship Graph

**Status: Not started**

**Prerequisite: Phase 2 gate met.**

Builds a static entity-relationship graph from the news corpus and gives the Retriever a traversal tool for cross-sector reasoning.

### New files

| File | Purpose |
|------|---------|
| `backend/migrations/003_entity_relationships.sql` | Entity relationships table |
| `script/build_graph.py` | Extract entity-relationship triples from news corpus |
| `backend/tools/graph_tools.py` | `@tool traverse_entity_graph(entity, hops)` |

### Graph construction

Pre-built at setup time (not query time). The script extracts entity-relationship triples from news articles using the LLM:

- Entities: companies, sectors, events, products
- Relationships: `affects`, `supplies`, `competes_with`, `benefits_from`, `threatened_by`

### Gate criteria

- Graph seeded with 30+ relationship rows
- Retriever calls `traverse_entity_graph` in 2+ of 4 questions
- Relational Recall avg > 3.0
- Responses contain explicit multi-hop causal chains

## Phase 4: `critic` — Adversarial Critic + Revision

**Status: Not started**

**Prerequisite: Phase 3 gate met.**

Wires the Critic agent into the pipeline. After the Strategist recommends, the Critic challenges, then the Strategist revises.

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

### Gate criteria (final)

- Full pipeline runs: Retriever → Strategist → Critic → Revision
- All 5 dimensions avg > Phase 3 avg
- Actionability avg > 3.5
- Responses include dissenting perspective
- Full eval report shows monotonic improvement across all stages

## API Endpoints

The FastAPI entry points are defined in [backend/app.py](../backend/app.py).

### `POST /api/agent`

General-purpose agent endpoint. Routes through the pipeline when implemented (Phase 1+), falls back to the flat advisor at baseline.

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
  "tools_called": ["get_stock_price", "query_news_articles"],
  "pipeline_stages": ["retriever", "strategist"],
  "critique_summary": "..."
}
```

`pipeline_stages` and `critique_summary` are added in Phases 1 and 4 respectively.

### `POST /api/report-agent`

Dedicated report-agent endpoint. Not part of the pipeline.

Request body:

```json
{
  "query": "Download NVIDIA's 10-K, embed it, and retrieve the risk factors section."
}
```

This always routes to `financial_reports_embedding_specialist`.

## Portfolio Dependency

The advisor-facing portfolio context comes from [backend/portfolio.py](../backend/portfolio.py), which keeps:

- The static portfolio membership (8 holdings)
- The latest retrieved market snapshot
- Helper accessors for portfolio-wide and per-symbol reads

## Operational Notes

- The report tools currently use Supabase for persistent vector storage.
- TOC detection and section-map generation still rely on structured JSON responses.
- Section content generation relies on plain text responses for embedding.
- The pipeline orchestrator (`pipeline.py`) is added in Phase 1 and extended in each subsequent phase.
