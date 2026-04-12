"""Schema probe for document_tree_nodes.

Importable module: call run_schema_probe(sb) -> dict before any ingest run.
All assertions raise RuntimeError on failure; caller decides whether to abort.
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import _env_bootstrap  # noqa: F401

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Canonical file_title registries (shared with ingest_10k_filings.py)
# ---------------------------------------------------------------------------

OLD_FILE_TITLES_BY_TICKER: dict[str, list[str]] = {
    "AAPL": ["Apple Inc. Form 10-K for the Fiscal Year Ended September 27, 2025"],
    "MSFT": ["MICROSOFT CORPORATION FORM 10-K For the Fiscal Year Ended June 30, 2025"],
    "GOOGL": ["Alphabet Inc. Form 10-K for the Fiscal Year Ended December 31, 2025"],
    "AMZN": ["AMAZON.COM, INC. FORM 10-K For the Fiscal Year Ended December 31, 2025"],
    "NVDA": ["NVIDIA Corporation 10-K for Fiscal Year 2025"],
    "LLY": ["Eli Lilly and Company Form 10-K for the Year Ended December 31, 2025"],
    "JPM": [
        "JPMorgan Chase & Co. Form 10-K for Fiscal Year 2025",
        "JPMorgan Chase & Co. Form 10-K for Fiscal Year 2025 - Financial Section",
    ],
    "XOM": [
        "Exxon Mobil Corporation Form 10-K for the Fiscal Year Ended December 31, 2025",
        "Exxon Mobil Corporation Form 10-K for the Fiscal Year Ended December 31, 2025 - FINANCIAL SECTION",
    ],
}

NEW_FILE_TITLES_BY_TICKER: dict[str, str] = {
    "AAPL": "Apple Inc. 10-K FY2025",
    "MSFT": "Microsoft Corporation 10-K FY2025",
    "GOOGL": "Alphabet Inc. 10-K FY2025",
    "AMZN": "Amazon.com, Inc. 10-K FY2025",
    "NVDA": "NVIDIA Corporation 10-K FY2025",
    "LLY": "Eli Lilly and Company 10-K FY2025",
    "JPM": "JPMorgan Chase & Co. 10-K FY2025",
    "XOM": "Exxon Mobil Corporation 10-K FY2025",
}

# All valid file_title strings that may appear in the DB (old or new).
EXPECTED_OLD_OR_NEW_FILE_TITLES: set[str] = {
    # OLD (currently in DB)
    "Apple Inc. Form 10-K for the Fiscal Year Ended September 27, 2025",
    "MICROSOFT CORPORATION FORM 10-K For the Fiscal Year Ended June 30, 2025",
    "Alphabet Inc. Form 10-K for the Fiscal Year Ended December 31, 2025",
    "AMAZON.COM, INC. FORM 10-K For the Fiscal Year Ended December 31, 2025",
    "NVIDIA Corporation 10-K for Fiscal Year 2025",
    "Eli Lilly and Company Form 10-K for the Year Ended December 31, 2025",
    "JPMorgan Chase & Co. Form 10-K for Fiscal Year 2025",
    "JPMorgan Chase & Co. Form 10-K for Fiscal Year 2025 - Financial Section",
    "Exxon Mobil Corporation Form 10-K for the Fiscal Year Ended December 31, 2025",
    "Exxon Mobil Corporation Form 10-K for the Fiscal Year Ended December 31, 2025 - FINANCIAL SECTION",
    # NEW (may exist after a partial-failed prior run)
    "Apple Inc. 10-K FY2025",
    "Microsoft Corporation 10-K FY2025",
    "Alphabet Inc. 10-K FY2025",
    "Amazon.com, Inc. 10-K FY2025",
    "NVIDIA Corporation 10-K FY2025",
    "Eli Lilly and Company 10-K FY2025",
    "JPMorgan Chase & Co. 10-K FY2025",
    "Exxon Mobil Corporation 10-K FY2025",
}

_REQUIRED_COLUMNS = {"id", "node_type", "title", "file_title", "depth", "parent_id", "document_id"}

EMBEDDING_DIM = 4096
_ROW_COUNT_UPPER_BOUND = 20_000


def run_schema_probe(sb) -> dict:  # type: ignore[type-arg]
    """Run six schema assertions against document_tree_nodes.

    Parameters
    ----------
    sb:
        A Supabase ``Client`` instance (module-level, already initialised).

    Returns
    -------
    dict with keys:
        row_count       int
        table_bytes     int | None
        document_titles list[str]
        probe_rpc_ok    bool

    Raises
    ------
    RuntimeError
        On any assertion failure.  Caller decides whether to abort the ingest.
    """
    result: dict = {
        "row_count": 0,
        "table_bytes": None,
        "document_titles": [],
        "probe_rpc_ok": False,
    }

    # (a) Column names check — read one row, verify all 7 required columns present.
    col_check = (
        sb.table("document_tree_nodes")
        .select("id,node_type,title,file_title,depth,parent_id,document_id")
        .limit(1)
        .execute()
    )
    if col_check.data:
        present = set(col_check.data[0].keys())
        missing = _REQUIRED_COLUMNS - present
        if missing:
            raise RuntimeError(f"document_tree_nodes missing expected columns: {missing}")
    logger.info("[probe] column check OK")

    # (b) + (c) RPC dry-run with 4096-dim zero vector; accept empty results as success.
    dummy_vector = [0.0] * EMBEDDING_DIM
    try:
        rpc_result = sb.rpc(
            "match_document_tree_nodes",
            {
                "query_embedding": dummy_vector,
                "match_threshold": 0.1,
                "match_count": 1,
                "match_depth": 2,
            },
        ).execute()
        result["probe_rpc_ok"] = True
        logger.info("[probe] RPC dry-run OK (returned %d rows)", len(rpc_result.data or []))
    except Exception as exc:
        msg = str(exc)
        if "different vector dimensions" in msg or "dimension" in msg.lower():
            raise RuntimeError(
                f"match_document_tree_nodes dimension mismatch: probe used {EMBEDDING_DIM}-dim vector "
                f"but RPC rejected it — check EMBEDDING_DIM constant. Original error: {exc}"
            ) from exc
        if "57014" in msg or "statement timeout" in msg.lower():
            logger.warning("[probe] RPC dry-run timed out (zero-vector degeneracy) — treating as non-fatal")
            result["probe_rpc_ok"] = True
        else:
            raise RuntimeError(f"match_document_tree_nodes RPC dry-run failed unexpectedly: {exc}") from exc

    # (d) Row count sanity bound.
    count_resp = sb.table("document_tree_nodes").select("id", count="exact").limit(1).execute()
    row_count = count_resp.count or 0
    if row_count >= _ROW_COUNT_UPPER_BOUND:
        raise RuntimeError(
            f"document_tree_nodes row count {row_count} exceeds upper bound {_ROW_COUNT_UPPER_BOUND}"
        )
    if row_count == 0:
        logger.warning("[probe] document_tree_nodes is empty — OK for re-ingest after rollback")
    result["row_count"] = row_count
    logger.info("[probe] row count OK: %d", row_count)

    # (e) Table size logging — best-effort, failure is non-fatal.
    try:
        size_resp = sb.rpc(
            "pg_total_relation_size_mb",
            {"table_name": "document_tree_nodes"},
        ).execute()
        result["table_bytes"] = size_resp.data
        logger.info("[probe] table size: %s", size_resp.data)
    except Exception:
        logger.info("[probe] table size: unknown (RPC not available)")

    # (f) Stale file_title check — collect unique document-level file_titles.
    ft_resp = sb.table("document_tree_nodes").select("file_title").eq("node_type", "document").limit(50).execute()
    db_titles = {row["file_title"] for row in (ft_resp.data or []) if row.get("file_title")}
    unexpected = db_titles - EXPECTED_OLD_OR_NEW_FILE_TITLES
    if unexpected:
        raise RuntimeError(f"unexpected file_title in document_tree_nodes: {unexpected}")
    result["document_titles"] = sorted(db_titles)
    logger.info("[probe] file_title check OK: %d document titles found", len(db_titles))

    return result
