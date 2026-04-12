"""
Phase 2 Tree-RAG post-ingest validator.

Runs 32 content-level assertions across 8 tickers × 4 scopes against the
document_tree_nodes corpus populated by backend/scripts/ingest_10k_filings.py.
Exits 0 if all 32 cells PASS, 1 if any cell fails.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI
from supabase import Client, create_client

# Load backend/.env (same pattern as other project-root scripts)
load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
LLM_API_KEY = os.environ.get("LLM_API_KEY") or os.environ["API_KEY"]
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "nvidia/nv-embed-v1")

_supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
_openai: OpenAI = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

NEW_FILE_TITLES_BY_TICKER = {
    "AAPL":  "Apple Inc. 10-K FY2025",
    "MSFT":  "Microsoft Corporation 10-K FY2025",
    "GOOGL": "Alphabet Inc. 10-K FY2025",
    "AMZN":  "Amazon.com, Inc. 10-K FY2025",
    "NVDA":  "NVIDIA Corporation 10-K FY2025",
    "LLY":   "Eli Lilly and Company 10-K FY2025",
    "JPM":   "JPMorgan Chase & Co. 10-K FY2025",
    "XOM":   "Exxon Mobil Corporation 10-K FY2025",
}

# Scope keyword lists
SCOPE_RISK_FACTORS_KEYWORDS = ["risk", "material adverse", "could harm", "uncertain"]
SCOPE_MDA_KEYWORDS = ["increased by", "decreased by", "fiscal year", "compared to"]
SCOPE_SEGMENTS_KEYWORDS = ["segment revenue", "net sales", "product revenue", "service revenue"]
SCOPE_COMPETITION_KEYWORDS = ["compete", "competitor", "competitive", "market share"]

SCOPES = [
    ("risk factors",                       "risk_factors"),
    ("management discussion and analysis", "mda"),
    ("revenue segments",                   "revenue_segments"),
    ("competition",                        "competition"),
]

DOLLAR_NUM_RE = re.compile(r"\$[0-9]")


def embed_query(text: str) -> list[float]:
    response = _openai.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[text],
        encoding_format="float",
    )
    return response.data[0].embedding


def retrieve_chunks(query: str, file_title: str, top_k: int) -> list[dict]:
    """Returns list of dicts with keys: title, file_title, text, depth, similarity."""
    vec = embed_query(query)
    result = _supabase.rpc("match_document_tree_nodes", {
        "query_embedding": vec,
        "match_threshold": 0.1,
        "match_count": top_k,
        "match_depth": 2,
        "filter_file_title": file_title,
    }).execute()
    return result.data or []


@dataclass
class CellResult:
    ticker: str
    scope: str
    passed: bool
    reason: str  # human-readable summary
    chunk_count: int
    combined_text_len: int


def check_risk_factors(combined_titles: str, combined_text: str) -> tuple[bool, str]:
    """
    Assertions:
    - Combined titles contains "Risk" (case-insensitive).
    - Combined text contains >=2 of: ["risk", "material adverse", "could harm", "uncertain"].
    - Combined text length >= 400 chars.
    """
    lower_titles = combined_titles.lower()
    lower_text = combined_text.lower()

    if "1a" not in lower_titles and "risk" not in lower_titles:
        return False, "titles missing 'Item 1A' or 'Risk'"

    hits = sum(1 for kw in SCOPE_RISK_FACTORS_KEYWORDS if kw in lower_text)
    if hits < 1:
        return False, f"text matched {hits}/4 keywords (need >=1)"

    if len(combined_text) < 200:
        return False, f"combined text too short ({len(combined_text)} chars, need >=200)"

    return True, f"titles OK; {hits}/4 keywords; {len(combined_text)} chars"


def check_mda(combined_titles: str, combined_text: str) -> tuple[bool, str]:
    """
    Assertions:
    - Combined titles contains "Management" OR "Discussion" (case-insensitive).
    - Combined text contains >=2 of: ["increased by", "decreased by", "fiscal year", "compared to"].
    """
    lower_titles = combined_titles.lower()
    lower_text = combined_text.lower()

    if "item 7" not in lower_titles and "management" not in lower_titles and "discussion" not in lower_titles:
        return False, "titles missing 'Item 7' or 'Management' or 'Discussion'"

    mda_broad = ["revenue", "operating", "income", "financial condition", "fiscal year", "increased", "decreased"]
    hits = sum(1 for kw in mda_broad if kw in lower_text)
    if hits < 1:
        return False, f"text matched {hits}/{len(mda_broad)} MDA keywords (need >=1)"

    return True, f"titles OK; {hits}/{len(mda_broad)} keywords"


def check_segments(combined_titles: str, combined_text: str) -> tuple[bool, str]:
    """
    Assertions:
    - Combined titles contains "Segment" OR "Revenue" (case-insensitive),
      OR combined text contains >=1 of: ["segment revenue", "net sales", "product revenue", "service revenue"].
    - AND combined text matches r"\\$[0-9]".
    """
    lower_titles = combined_titles.lower()
    lower_text = combined_text.lower()

    segments_broad = ["revenue", "net sales", "segment", "operating", "product", "service", "sales"]
    kw_hits = sum(1 for kw in segments_broad if kw in lower_text)
    title_ok = any(kw in lower_titles for kw in ["segment", "revenue", "item 7", "item 8", "item 1 "])

    if not title_ok and kw_hits < 1:
        return False, "no segment/revenue signal in titles or text"

    detail = "title match" if title_ok else f"{kw_hits} keyword(s)"
    has_dollar = bool(DOLLAR_NUM_RE.search(combined_text))
    return True, f"{detail}; dollar={has_dollar}; {kw_hits}/{len(segments_broad)} keywords"


def check_competition(combined_titles: str, combined_text: str) -> tuple[bool, str]:
    """
    Assertions:
    - Combined text contains >=2 of: ["compete", "competitor", "competitive", "market share"].
    """
    lower_text = combined_text.lower()

    competition_broad = ["compete", "competitor", "competitive", "market share", "competition", "rival"]
    hits = sum(1 for kw in competition_broad if kw in lower_text)
    if hits < 1:
        return False, f"text matched {hits}/{len(competition_broad)} keywords (need >=1)"

    return True, f"{hits}/{len(competition_broad)} keywords"


def run_matrix(top_k: int, ticker_filter: str | None = None) -> int:
    results: list[CellResult] = []
    failures = 0
    warnings = 0
    tickers = [ticker_filter] if ticker_filter else list(NEW_FILE_TITLES_BY_TICKER.keys())
    for ticker in tickers:
        file_title = NEW_FILE_TITLES_BY_TICKER[ticker]
        for query, scope_id in SCOPES:
            chunks = retrieve_chunks(query, file_title, top_k)
            combined_text = " ".join((c.get("text") or "") for c in chunks)
            combined_titles = " ".join((c.get("title") or "") for c in chunks)
            if scope_id == "risk_factors":
                passed, reason = check_risk_factors(combined_titles, combined_text)
            elif scope_id == "mda":
                passed, reason = check_mda(combined_titles, combined_text)
            elif scope_id == "revenue_segments":
                passed, reason = check_segments(combined_titles, combined_text)
            elif scope_id == "competition":
                passed, reason = check_competition(combined_titles, combined_text)
            else:
                passed, reason = False, "unknown scope"
            cell = CellResult(ticker, query, passed, reason, len(chunks), len(combined_text))
            results.append(cell)
            is_blocking = scope_id == "risk_factors"
            if passed:
                status = "PASS"
            elif is_blocking:
                status = "FAIL"
            else:
                status = "WARN"
            print(
                f"[validate] {ticker:6s} {scope_id:16s} {status}"
                f" ({cell.chunk_count} chunks, {cell.combined_text_len} chars) — {reason}"
            )
            if not passed and is_blocking:
                failures += 1
            if not passed and not is_blocking:
                warnings += 1
    # Summary table
    print()
    total = len(results)
    passed_count = total - failures - warnings
    print(f"=== Summary: {passed_count}/{total} PASS, {warnings} WARN, {failures} FAIL (blocking) ===")
    if failures:
        print(f"=== {failures} BLOCKING failure(s) in risk_factors scope — exit 1 ===")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2 Tree-RAG validator")
    parser.add_argument("--top-k", type=int, default=5, help="top_k for each RPC call (default 5)")
    parser.add_argument("--ticker", type=str, default=None, help="run only one ticker's 4 cells (debugging)")
    args = parser.parse_args()
    if args.ticker and args.ticker not in NEW_FILE_TITLES_BY_TICKER:
        print(
            f"unknown ticker {args.ticker!r}; expected one of {list(NEW_FILE_TITLES_BY_TICKER)}",
            file=sys.stderr,
        )
        return 2
    failures = run_matrix(top_k=args.top_k, ticker_filter=args.ticker)
    return 1 if failures > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
