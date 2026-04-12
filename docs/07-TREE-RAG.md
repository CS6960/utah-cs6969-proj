# Tree RAG

This document describes the report-ingestion and retrieval flow implemented in
`backend/scripts/ingest_10k_filings.py` and mirrored by the backend report tools
in `backend/agent_tools/financial_reports_tools.py`.

## Terminology

- "document node" = node_type='document', depth=0, one per 10-K filing, file_title = the NEW canonical string
- "section node" = node_type='section', depth=1, one per passing 10-K Item (e.g., "Item 1A: Risk Factors"), parent_id = document node id
- "chunk node" = node_type='chunk', depth=2, leaves of the tree, the only nodes match_document_tree_nodes returns at match_depth=2
- "file_title" = authoritative ticker identifier in NEW_FILE_TITLES_BY_TICKER; must contain a Strategist alias substring from strategist_tools.py
- "length gate" = items with text length < 300 OR > 200000 are skipped (TRIZ separation-in-condition replacement for LLM validation)
- "two-phase commit" = Phase A (build all 8 in-memory payloads, DB untouched) → Phase B (schema probe, bulk delete, per-ticker insert + gate, coverage gate, rollback_all on any exception)

Cross-reference `internal/phase2_rag_rebuild.md` section headings where overlap exists.

## Goal

The tree RAG pipeline turns a 10-K filing into a hierarchical retrieval index with
three levels:

- `document`
- `section`
- `chunk`

This lets retrieval return the best leaf chunks while still preserving document and
section lineage for multi-hop context assembly.

## Ingest Pipeline

The ingest script at `backend/scripts/ingest_10k_filings.py` uses
**edgartools 5.28.5** as its extraction basis.

### Prerequisites

- `EDGAR_IDENTITY` must be set in `backend/.env` (e.g., `"Your Name your@email.com"`).
  The SEC EDGAR User-Agent rule requires a valid identity string in every request.
  `set_identity(EDGAR_IDENTITY)` is called at script startup before any EDGAR API
  call.

### Length Gate

Items with `len(text) < 300` or `len(text) > 200000` are skipped. This is a TRIZ
separation-in-condition replacement for LLM validation: structural noise (boilerplate
headers, exhibit stubs) is too short; pathological mega-sections are too long to
embed reliably. Only items that pass the gate become section nodes and produce chunks.

### Two-Phase Atomic-or-Nothing Commit

**Phase A** — build all 8 in-memory payloads. The database is not touched until
every ticker succeeds in memory. If any ticker fails to produce a valid payload,
the script exits before Phase B begins.

**Phase B** — atomic write:
1. Schema probe: verify `document_tree_nodes` exists and the RPC is callable.
2. Bulk DELETE of all rows matching the 18 old+new `file_title` strings (old
   canonical names and new canonical names).
3. Per-ticker INSERT with completeness gate: each ticker must insert at least one
   chunk node or the commit is aborted.
4. Cross-ticker coverage gate: an unfiltered `"risk factors"` top_k=8 query must
   return results for ≥7 of the 8 tickers.
5. `rollback_all()` on any exception — the bulk DELETE is re-applied in reverse to
   restore the prior state.

## Script Flow

The ingest flow in `backend/scripts/ingest_10k_filings.py` works in these stages:

1. Load filings via edgartools:
   ```python
   from edgar import Company, set_identity
   set_identity(EDGAR_IDENTITY)
   Company(ticker).get_filings(form="10-K").latest(1)
   ```
2. Access the typed `TenK` object via `.obj()`.
3. Dedupe `tenk.items` with `list(dict.fromkeys(...))` to remove duplicate item
   references that edgartools can surface for some filers.
4. Apply the **length gate**: items with `len(text) < 300` or `len(text) > 200000`
   chars are skipped.
5. Chunk passing items via
   `RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)`.
6. Build tree nodes using the `document_tree_nodes` schema (document → section →
   chunk hierarchy).
7. Embed via **nvidia/nv-embed-v1** (4096-dim) in batches of 20.
8. Two-phase atomic commit: Phase A builds all 8 in-memory payloads with the DB
   untouched; Phase B performs a bulk DELETE then per-ticker INSERT with the
   completeness gate and cross-ticker coverage gate, calling `rollback_all()` on
   any exception.

## file_title Contract

`file_title` is the authoritative ticker identifier stored in the `document` node
and propagated to all child nodes. It must contain a Strategist alias substring
(aliases defined in `backend/agent_tools/strategist_tools.py` lines 228–247) so
the Strategist agent can route RAG queries to the correct filing by ticker mention.

The ingest script asserts the alias-substring match at build time (Phase A) and
raises immediately if any canonical fails the check.

### NEW_FILE_TITLES_BY_TICKER

```
AAPL  → "Apple Inc. 10-K FY2025"
MSFT  → "Microsoft Corporation 10-K FY2025"
GOOGL → "Alphabet Inc. 10-K FY2025"
AMZN  → "Amazon.com, Inc. 10-K FY2025"
NVDA  → "NVIDIA Corporation 10-K FY2025"
LLY   → "Eli Lilly and Company 10-K FY2025"
JPM   → "JPMorgan Chase & Co. 10-K FY2025"
XOM   → "Exxon Mobil Corporation 10-K FY2025"
```

Each canonical string must contain a Strategist alias substring. For example,
`"Apple Inc. 10-K FY2025"` contains `"Apple"`, which is an alias for AAPL in
`strategist_tools.py`.

## Tree Shape

Each indexed report becomes a small tree:

1. One root `document` node
2. One `section` node per filing section that passes the length gate
3. Many `chunk` nodes under each section

Important node fields:

- `id`
- `document_id` or `report_id`
- `parent_id`
- `node_type`
- `depth`
- `sequence`
- `title`
- `filename`
- `text`
- `metadata`
- `embedding`

The root node stores a compact document outline. Section nodes store the full
section text plus a short summary-oriented embedding input. Chunk nodes store the
chunk text used for retrieval.

## Embedding Strategy

Embedding text is built in a consistent format:

```text
Title: <section title>
Filename: <pdf filename>
Text: <chunk or summary text>
```

This gives the vector store access to:

- the section title
- the source filename
- the content itself

Embeddings use **nvidia/nv-embed-v1** which produces **4096-dimensional** vectors.

## Chunking Strategy

The pipeline uses `RecursiveCharacterTextSplitter` with semantic separators,
favoring:

- paragraph boundaries
- line boundaries
- sentence boundaries
- JSON-like separators such as `},` and `],`

Leaf embedding chunks use `chunk_size=800, chunk_overlap=150`.

## Retrieval Flow

Retrieval works like this:

1. Embed the user query.
2. Search chunk nodes with `match_document_tree_nodes`.
3. Fetch parent nodes with `fetch_lineage(...)`.
4. Return chunk text together with `document -> section -> chunk` lineage.

This makes it possible to answer with both a precise chunk and its surrounding
section/document context.

## Backend Mirror

The backend mirrors the same ideas in
`backend/agent_tools/financial_reports_tools.py`:

- report data is kept in `REPORT_STORE`
- embedded nodes are kept in `EMBEDDED_REPORT_STORE`
- `_build_report_tree_nodes(...)` creates the same document/section/chunk hierarchy
- `retrieve_embedded_financial_report_info(...)` returns chunk matches plus lineage

The backend version is in-memory, while the standalone script writes to Supabase.

## Expected Storage Contract

The script expects a vector table named `document_tree_nodes` and an RPC named
`match_document_tree_nodes`.

At a minimum, the table needs to support:

- identifiers and parent pointers
- node type and depth
- text and metadata
- a vector embedding column (4096-dim for nvidia/nv-embed-v1)

The retrieval RPC is expected to:

- compare the query embedding to stored vectors
- filter to the requested depth, usually chunk depth
- return the highest-scoring matches
