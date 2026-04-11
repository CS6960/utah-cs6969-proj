from __future__ import annotations

import logging
import os
from typing import Any

from langchain.tools import tool
from openai import OpenAI

import _env_bootstrap  # noqa: F401  -- loads backend/.env before env vars are read below
from supabase import Client, create_client

logger = logging.getLogger(__name__)

LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("API_KEY")
LLM_BASE_URL = os.getenv("LLM_BASE_URL") or os.getenv("BASE_URL", "https://integrate.api.nvidia.com/v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nvidia/nv-embed-v1")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def _get_client() -> OpenAI:
    if not LLM_API_KEY:
        raise ValueError("LLM_API_KEY is not configured.")
    return OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)


if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL or SUPABASE_KEY is not configured.")

_supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def _embed_query(query: str) -> list[float]:
    client = _get_client()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[query],
        encoding_format="float",
    )
    return response.data[0].embedding


@tool
def list_available_financial_reports() -> dict:
    """
    List available financial reports from document_tree_nodes by selecting document-level nodes.
    """
    result = _supabase.table("document_tree_nodes").select("file_title").eq("node_type", "document").limit(50).execute()
    file_titles = sorted({row.get("file_title") for row in (result.data or []) if row.get("file_title")})
    reports = [{"file_title": file_title} for file_title in file_titles]
    logger.info("Listed available reports from document_tree_nodes. total_reports=%s", len(reports))
    return {"total_reports": len(reports), "reports": reports}


@tool
def retrieve_embedded_financial_report_info(
    query: str,
    file_title: str = "",
    top_k: int = 5,
    match_depth: int = 2,
) -> dict:
    """
    Retrieve relevant report content using server-side similarity search
    via the match_document_tree_nodes RPC, avoiding bulk embedding transfers.
    """
    logger.info(
        "Retrieving embedded report info. file_title=%s top_k=%s query_preview=%s",
        file_title,
        top_k,
        query[:120],
    )
    query_embedding = _embed_query(query)
    returned_count = max(1, int(top_k))

    # Use server-side similarity search (avoids transferring all embeddings)
    rpc_params: dict[str, Any] = {
        "query_embedding": query_embedding,
        "match_threshold": 0.1,
        "match_count": returned_count,
        "match_depth": match_depth,
        "filter_file_title": file_title or None,
    }
    matches_result = _supabase.rpc("match_document_tree_nodes", rpc_params).execute()
    raw_matches = matches_result.data or []

    if not raw_matches:
        logger.warning("match_document_tree_nodes returned no results.")
        return {"error": "No matching document nodes found."}

    scored_matches = []
    for match in raw_matches:
        scored_matches.append(
            {
                "title": match.get("title"),
                "file_title": match.get("file_title"),
                "text": match.get("text"),
                "metadata": match.get("metadata"),
                "depth": match.get("depth"),
                "node_type": match.get("node_type"),
                "score": round(float(match.get("similarity", 0)), 4),
            }
        )

    logger.info(
        "Retrieved embedded report matches via RPC. returned=%s",
        len(scored_matches),
    )
    return {
        "query": query,
        "matches": scored_matches[:returned_count],
    }
