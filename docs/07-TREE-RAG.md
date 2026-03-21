# Tree RAG

This document describes the report-ingestion and retrieval flow implemented in [script/test_10k_llm_nvd.py](/Users/zhihao/personal_projects/utah-cs6969-proj/script/test_10k_llm_nvd.py) and mirrored by the backend report tools in [backend/tools/financial_reports_tools.py](/Users/zhihao/personal_projects/utah-cs6969-proj/backend/tools/financial_reports_tools.py).

## Goal

The tree RAG pipeline turns a financial report PDF into a hierarchical retrieval index with three levels:

- `document`
- `section`
- `chunk`

This lets retrieval return the best leaf chunks while still preserving document and section lineage for multi-hop context assembly.

## Script Flow

The notebook/script flow in [script/test_10k_llm_nvd.py](/Users/zhihao/personal_projects/utah-cs6969-proj/script/test_10k_llm_nvd.py) works in these stages:

1. Load the PDF with `fitz`.
2. Use `find_toc_page(...)` to identify the table-of-contents page.
3. Use `create_section_map(...)` to produce structured section boundaries with `part`, `item`, `title`, `start_page`, and `end_page`.
4. Extract each section's raw text with `get_pdf_text_range(...)`.
5. Use `process_section_to_rag_format(...)` to convert each section into plain text suitable for embedding.
6. Build `final_rag_payload`, where each entry contains:
   - `title`
   - `content`
   - `metadata`
7. Convert the payload into tree nodes with `build_tree_nodes(...)`.
8. Embed and insert those nodes into `document_tree_nodes`.
9. Retrieve chunk matches through `match_document_tree_nodes` and reconstruct lineage with `fetch_lineage(...)`.

## Tree Shape

Each indexed report becomes a small tree:

1. One root `document` node
2. One `section` node per filing section
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

The root node stores a compact document outline. Section nodes store the full section text plus a short summary-oriented embedding input. Chunk nodes store the chunk text used for retrieval.

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

Large sections are summarized before section-level embedding so the embedding model does not receive oversized inputs.

## Chunking Strategy

The pipeline uses `RecursiveCharacterTextSplitter` with semantic separators, favoring:

- paragraph boundaries
- line boundaries
- sentence boundaries
- JSON-like separators such as `},` and `],`

Section chunking and leaf chunking use different sizes:

- section processing chunks: larger, for LLM transformation
- leaf embedding chunks: smaller, for vector retrieval

The section-processing prompt returns plain text, not JSON, so `final_rag_payload["content"]` is directly embeddable.

## Retrieval Flow

Retrieval in the script works like this:

1. Embed the user query
2. Search chunk nodes with `match_document_tree_nodes`
3. Fetch parent nodes with `fetch_lineage(...)`
4. Return chunk text together with `document -> section -> chunk` lineage

This makes it possible to answer with both a precise chunk and its surrounding section/document context.

## Backend Mirror

The backend mirrors the same ideas in [backend/tools/financial_reports_tools.py](/Users/zhihao/personal_projects/utah-cs6969-proj/backend/tools/financial_reports_tools.py):

- report data is kept in `REPORT_STORE`
- embedded nodes are kept in `EMBEDDED_REPORT_STORE`
- `_build_report_tree_nodes(...)` creates the same document/section/chunk hierarchy
- `retrieve_embedded_financial_report_info(...)` returns chunk matches plus lineage

The backend version is in-memory, while the standalone script writes to Supabase.

## Expected Storage Contract

The script expects a vector table named `document_tree_nodes` and an RPC named `match_document_tree_nodes`.

At a minimum, the table needs to support:

- identifiers and parent pointers
- node type and depth
- text and metadata
- a vector embedding column

The retrieval RPC is expected to:

- compare the query embedding to stored vectors
- filter to the requested depth, usually chunk depth
- return the highest-scoring matches

## Practical Notes

- `find_toc_page(...)` and `create_section_map(...)` still use structured JSON because the rest of the pipeline depends on exact fields.
- section transformation now returns plain text strings, not JSON objects.
- if you rerun the notebook after code changes, restart the kernel so old in-memory cell definitions do not shadow the saved code.
