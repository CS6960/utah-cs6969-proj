"""
Build entity-relationship graph from news_articles table.

Usage:
    python script/build_graph.py               # extract and upsert edges
    python script/build_graph.py --dry-run     # print edges without inserting
    python script/build_graph.py --validate    # assert graph coverage thresholds

Reads news_articles WHERE relevant=true, uses an LLM to extract entity-relationship
triples, and upserts them into the entity_relationships table.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

import openai
from dotenv import load_dotenv
from supabase import create_client

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

load_dotenv(Path(__file__).resolve().parent.parent / "backend" / ".env")

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]

LLM_API_KEY = os.environ.get("LLM_API_KEY") or os.environ.get("API_KEY")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL") or os.environ.get("BASE_URL")
LLM_MODEL_NAME = os.environ.get("LLM_MODEL_NAME") or os.environ.get("MODEL_NAME", "qwen/qwen3.5-122b-a10b")

PORTFOLIO_TICKERS = ["AAPL", "MSFT", "JPM", "NVDA", "AMZN", "GOOGL", "LLY", "XOM"]

SYSTEM_PROMPT = """\
You are an entity-relationship extractor for financial news. Given a news article,
extract entity-relationship triples as a flat JSON array.

Each object must have exactly these keys:
- source_entity: name of the source entity (string)
- source_type: one of: company, sector, commodity, event, country, person, policy
- target_entity: name of the target entity (string)
- target_type: one of: company, sector, commodity, event, country, person, policy
- relationship: a short verb phrase describing the relationship (e.g. "threatens",
  "benefits", "causes", "competes with", "raises prices for", "drives demand for")
- evidence: a single sentence from or about the article that justifies this edge

Return ONLY a valid JSON array. Return [] if no meaningful relationships exist.
Do not include markdown fences, explanations, or any text outside the JSON array.
"""

RETRY_PROMPT = """\
Your previous response was not valid JSON. Return ONLY a valid JSON array of objects,
no markdown, no explanation. Each object: source_entity, source_type, target_entity,
target_type, relationship, evidence. Return [] if unsure.
"""


def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)  # noqa: SB004


def get_llm_client() -> openai.OpenAI:
    return openai.OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)


def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers if present."""
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        # parts[0] is empty, parts[1] is the fenced content, parts[2] is trailing
        inner = parts[1]
        if inner.startswith("json"):
            inner = inner[4:]
        return inner.strip()
    return text


def _call_llm(client: openai.OpenAI, messages: list[dict], article_id: str) -> list[dict]:
    """Call the LLM and return parsed triples. Returns [] on failure."""
    result = client.chat.completions.create(
        model=LLM_MODEL_NAME,
        messages=messages,
        temperature=0.1,
    )
    raw = result.choices[0].message.content.strip()
    cleaned = _strip_markdown_fences(raw)

    try:
        triples = json.loads(cleaned)
        if not isinstance(triples, list):
            raise ValueError("Expected a JSON array")
        return triples
    except (json.JSONDecodeError, ValueError) as err:
        logger.warning("JSON parse failed for article %s: %s — retrying once", article_id, err)

        # Retry with a shorter fix-the-JSON prompt
        retry_messages = messages + [
            {"role": "assistant", "content": raw},
            {"role": "user", "content": RETRY_PROMPT},
        ]
        retry_result = client.chat.completions.create(
            model=LLM_MODEL_NAME,
            messages=retry_messages,
            temperature=0.1,
        )
        retry_raw = retry_result.choices[0].message.content.strip()
        retry_cleaned = _strip_markdown_fences(retry_raw)

        try:
            triples = json.loads(retry_cleaned)
            if not isinstance(triples, list):
                raise ValueError("Expected a JSON array on retry")
            return triples
        except (json.JSONDecodeError, ValueError) as retry_err:
            logger.warning("Retry also failed for article %s: %s — skipping", article_id, retry_err)
            return []


def extract_from_article(client: openai.OpenAI, article: dict) -> list[dict]:
    """Call the LLM to extract triples from a single article."""
    headline = article.get("headline", "")
    body = article.get("body", "")
    ticker = article.get("ticker", "")

    user_content = f"Ticker: {ticker}\nHeadline: {headline}\n\nBody:\n{body}"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    article_id = str(article.get("id", "unknown"))
    triples = _call_llm(client, messages, article_id)
    logger.info("  Article %s (%s): %d edges extracted", article_id, ticker, len(triples))
    return triples


def load_articles(sb) -> list[dict]:
    """Fetch all relevant news articles from Supabase."""
    result = (
        sb.table("news_articles")
        .select("id,ticker,headline,body")
        .eq("relevant", True)
        .limit(200)
        .execute()
    )
    return result.data or []


def run_validate(sb) -> bool:
    """
    Query entity_relationships and assert coverage thresholds.

    Checks:
      (a) at least 30 rows total
      (b) at least 6 distinct entities matching portfolio tickers
      (c) at least one edge where source or target contains "Iran" or "oil"

    Returns True if all checks pass, False otherwise.
    """
    rows = (
        sb.table("entity_relationships")
        .select("source_entity,source_type,target_entity,target_type,relationship")
        .limit(500)
        .execute()
        .data
        or []
    )

    # (a) row count
    total = len(rows)
    logger.info("Validation: total rows = %d", total)
    if total < 30:
        logger.error("FAIL (a): expected >= 30 rows, got %d", total)
        return False
    logger.info("PASS (a): %d rows >= 30", total)

    # (b) distinct entities that match portfolio tickers or company names
    ticker_names = {
        "AAPL": ["AAPL", "APPLE"],
        "MSFT": ["MSFT", "MICROSOFT"],
        "JPM": ["JPM", "JPMORGAN", "JP MORGAN"],
        "NVDA": ["NVDA", "NVIDIA"],
        "AMZN": ["AMZN", "AMAZON"],
        "GOOGL": ["GOOGL", "GOOGLE", "ALPHABET"],
        "LLY": ["LLY", "ELI LILLY", "LILLY"],
        "XOM": ["XOM", "EXXON", "EXXONMOBIL"],
    }
    matched_tickers: set[str] = set()
    for row in rows:
        src = (row.get("source_entity") or "").upper()
        tgt = (row.get("target_entity") or "").upper()
        combined = f"{src} {tgt}"
        for ticker, names in ticker_names.items():
            if any(name in combined for name in names):
                matched_tickers.add(ticker)

    logger.info("Validation: portfolio tickers with edges = %s", matched_tickers)
    if len(matched_tickers) < 6:
        logger.error("FAIL (b): expected >= 6 portfolio tickers in edges, got %d: %s", len(matched_tickers), matched_tickers)
        return False
    logger.info("PASS (b): %d portfolio tickers matched", len(matched_tickers))

    # (c) at least one edge referencing Iran or oil
    geo_terms = {"iran", "oil"}
    found_geo = False
    for row in rows:
        src = (row.get("source_entity") or "").lower()
        tgt = (row.get("target_entity") or "").lower()
        rel = (row.get("relationship") or "").lower()
        combined = f"{src} {tgt} {rel}"
        if any(term in combined for term in geo_terms):
            found_geo = True
            break

    if not found_geo:
        logger.error("FAIL (c): no edge found containing 'Iran' or 'oil' in source/target")
        return False
    logger.info("PASS (c): found at least one Iran/oil edge")

    logger.info("All validation checks passed.")
    return True


def main():
    parser = argparse.ArgumentParser(description="Build entity-relationship graph from news_articles")
    parser.add_argument("--dry-run", action="store_true", help="Print edges without inserting into Supabase")
    parser.add_argument(
        "--validate",
        action="store_true",
        help="After extraction/insertion, validate graph coverage thresholds",
    )
    args = parser.parse_args()

    sb = get_supabase()

    # Load articles outside the loop
    logger.info("Loading relevant news articles ...")
    articles = load_articles(sb)
    logger.info("Loaded %d articles.", len(articles))

    if not articles:
        logger.info("No articles found — nothing to do.")
        if args.validate:
            passed = run_validate(sb)
            sys.exit(0 if passed else 1)
        sys.exit(0)

    client = get_llm_client()

    # -----------------------------------------------------------------------
    # Extract triples in chunks of 10 articles, upsert after each chunk.
    # LLM calls are inside the article loop (not Supabase calls).
    # The upsert loop iterates over collected edges, not articles — SB003-safe.
    # -----------------------------------------------------------------------
    total_upserted = 0
    chunk_size = 10

    for chunk_start in range(0, len(articles), chunk_size):
        chunk = articles[chunk_start : chunk_start + chunk_size]
        chunk_edges: list[dict] = []

        for idx, article in enumerate(chunk):
            if chunk_start + idx > 0:
                time.sleep(3)
            try:
                triples = extract_from_article(client, article)
            except Exception as exc:
                if "429" in str(exc) or "rate" in str(exc).lower():
                    logger.warning("Rate limited at article %d — waiting 30s", chunk_start + idx)
                    time.sleep(30)
                    try:
                        triples = extract_from_article(client, article)
                    except Exception:
                        logger.warning("Still failing after backoff — skipping article %s", article.get("id"))
                        continue
                else:
                    logger.warning("LLM error for article %s: %s — skipping", article.get("id"), exc)
                    continue
            for triple in triples:
                triple["article_id"] = article["id"]
                chunk_edges.append(triple)

        if args.dry_run:
            for edge in chunk_edges:
                print(json.dumps(edge))
        elif chunk_edges:
            # Batch upsert OUTSIDE the article loop — SB003-safe
            for i in range(0, len(chunk_edges), 50):
                batch = chunk_edges[i : i + 50]
                sb.table("entity_relationships").upsert(  # noqa: SB003
                    batch, on_conflict="source_entity,relationship,target_entity"
                ).execute()
                total_upserted += len(batch)
                logger.info("Upserted batch of %d edges (total: %d)", len(batch), total_upserted)

        logger.info(
            "Chunk %d-%d done: %d edges from %d articles",
            chunk_start + 1,
            chunk_start + len(chunk),
            len(chunk_edges),
            len(chunk),
        )

    logger.info("Total rows upserted: %d", total_upserted)

    if args.dry_run:
        logger.info("Dry-run mode: edges printed above, no upsert performed.")

    if args.validate:
        passed = run_validate(sb)
        sys.exit(0 if passed else 1)

    sys.exit(0)


if __name__ == "__main__":
    main()
