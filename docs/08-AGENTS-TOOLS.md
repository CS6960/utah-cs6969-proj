# Agents And Tools

This document describes the backend agents, their tools, and the API routes that expose them.

## Files

Core files:

- [backend/agents.py](/Users/zhihao/personal_projects/utah-cs6969-proj/backend/agents.py)
- [backend/tools/tools.py](/Users/zhihao/personal_projects/utah-cs6969-proj/backend/tools/tools.py)
- [backend/tools/financial_reports_tools.py](/Users/zhihao/personal_projects/utah-cs6969-proj/backend/tools/financial_reports_tools.py)
- [backend/app.py](/Users/zhihao/personal_projects/utah-cs6969-proj/backend/app.py)
- [backend/portfolio.py](/Users/zhihao/personal_projects/utah-cs6969-proj/backend/portfolio.py)

## Agent Roles

Two agent roles are currently registered in [backend/agents.py](/Users/zhihao/personal_projects/utah-cs6969-proj/backend/agents.py):

### `financial_advisor`

Purpose:

- answer portfolio questions
- discuss holdings, concentration, and performance
- use live or cached portfolio market data when available

Behavior:

- grounded in the user's portfolio
- concise and analytical
- should not invent holdings, prices, or unsupported conclusions

### `financial_reports_embedding_specialist`

Purpose:

- process SEC filings and other report PDFs
- build retrieval-ready report state
- retrieve relevant passages from embedded reports

Behavior:

- works step by step through the report-tool workflow
- references `report_id` explicitly
- avoids inventing report contents or retrieval output

## Tool Registry

The tool lists live in [backend/tools/tools.py](/Users/zhihao/personal_projects/utah-cs6969-proj/backend/tools/tools.py).

### Advisor Tools

`ADVISOR_TOOLS` currently includes:

- `DuckDuckGoSearchResults`
- `YahooFinanceNewsTool`
- `get_stock_price`
- `retrieve_embedded_financial_report_info`

This lets the advisor answer:

- market and news questions
- single-stock price checks
- questions that cite already embedded financial reports

### Report Tools

`REPORT_TOOLS` currently includes:

- `download_financial_report`
- `find_financial_report_table_of_contents`
- `create_financial_report_section_map`
- `embed_financial_report_content`
- `retrieve_embedded_financial_report_info`

This toolset is intentionally sequential.

## Report Tool Workflow

The expected workflow for the report specialist is:

1. `download_financial_report(pdf_url)`
2. `find_financial_report_table_of_contents(report_id)`
3. `create_financial_report_section_map(report_id)`
4. `embed_financial_report_content(report_id)`
5. `retrieve_embedded_financial_report_info(report_id, query, top_k=5)`

### `download_financial_report`

Downloads the PDF, extracts per-page text, derives the filename, and creates a new in-memory `report_id`.

Returns:

- `report_id`
- `pdf_url`
- `filename`
- `page_count`

### `find_financial_report_table_of_contents`

Uses the first pages of the report to identify the TOC page and stores both:

- `toc_page`
- `toc_text`

### `create_financial_report_section_map`

Runs the TOC parser and stores a structured section map with:

- `part`
- `item`
- `title`
- `start_page`
- `end_page`

### `embed_financial_report_content`

Builds the final report payload and the in-memory tree index.

For each section it stores:

- `title`
- `content` as plain text
- `metadata`

It then creates:

- one document node
- one section node per filing section
- chunk nodes for retrieval

### `retrieve_embedded_financial_report_info`

Embeds the query, scores stored chunk embeddings by cosine similarity, and returns:

- the matched chunk text
- the filename
- metadata
- `document -> section -> chunk` lineage
- similarity score

## API Endpoints

The FastAPI entry points are defined in [backend/app.py](/Users/zhihao/personal_projects/utah-cs6969-proj/backend/app.py).

### `POST /api/agent`

General-purpose agent endpoint.

Request body:

```json
{
  "query": "What is my portfolio concentration risk?",
  "role": "financial_advisor"
}
```

If `role` is omitted, the backend defaults to `financial_advisor`.

### `POST /api/report-agent`

Dedicated report-agent endpoint.

Request body:

```json
{
  "query": "Download NVIDIA's 10-K, embed it, and retrieve the risk factors section."
}
```

This always routes to `financial_reports_embedding_specialist`.

## Portfolio Dependency

The advisor-facing portfolio context comes from [backend/portfolio.py](/Users/zhihao/personal_projects/utah-cs6969-proj/backend/portfolio.py), which keeps:

- the static portfolio membership
- the latest retrieved market snapshot
- helper accessors for portfolio-wide and per-symbol reads

That portfolio state is separate from the report-ingestion state in `REPORT_STORE` and `EMBEDDED_REPORT_STORE`.

## Operational Notes

- The report tools currently use in-memory stores, so report state is lost on backend restart.
- The standalone script uses Supabase for persistent vector storage, while the backend tool path currently does not.
- TOC detection and section-map generation still rely on structured JSON responses.
- Section content generation now relies on plain text responses so the downstream payload is easier to embed and inspect.
