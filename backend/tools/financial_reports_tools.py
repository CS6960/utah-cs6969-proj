from __future__ import annotations

import json
import logging
import math
import os
from typing import Any

from dotenv import load_dotenv
from langchain.tools import tool
from openai import OpenAI
from supabase import Client, create_client

load_dotenv()
logger = logging.getLogger(__name__)

API_KEY = os.getenv("API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nvidia/nv-embed-v1")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")


def _get_client() -> OpenAI:
    if not API_KEY:
        raise ValueError("API_KEY is not configured.")
    return OpenAI(api_key=API_KEY, base_url="https://integrate.api.nvidia.com/v1")


def _get_supabase_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL or SUPABASE_KEY is not configured.")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def _embed_query(query: str) -> list[float]:
    client = _get_client()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[query],
        encoding_format="float",
    )
    return response.data[0].embedding


def _parse_embedding(embedding_value: Any) -> list[float] | None:
    if embedding_value is None:
        return None
    if isinstance(embedding_value, list):
        return [float(value) for value in embedding_value]
    if isinstance(embedding_value, str):
        try:
            parsed = json.loads(embedding_value)
            if isinstance(parsed, list):
                return [float(value) for value in parsed]
        except Exception:
            return None
    return None


def _cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(vector_a, vector_b, strict=False))
    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))
    if not norm_a or not norm_b:
        return 0.0
    return dot_product / (norm_a * norm_b)


def _node_type(node: dict[str, Any]) -> str | None:
    metadata = node.get("metadata") or {}
    return node.get("node_type") or metadata.get("node_type")


def _build_node_lineage(node_lookup: dict[str, dict[str, Any]], node_id: str) -> list[dict[str, Any]]:
    lineage = []
    current = node_lookup.get(node_id)

    while current:
        lineage.append(
            {
                "id": current["id"],
                "node_type": _node_type(current),
                "title": current.get("title"),
                "file_title": current.get("file_title"),
                "depth": current.get("depth"),
                "metadata": current.get("metadata"),
            }
        )
        parent_id = current.get("parent_id")
        current = node_lookup.get(parent_id) if parent_id else None

    lineage.reverse()
    return lineage


@tool
def list_available_financial_reports() -> dict:
    """
    List available financial reports from document_tree_nodes by selecting document-level nodes.
    """
    supabase = _get_supabase_client()
    result = supabase.table("document_tree_nodes").select("file_title").eq("node_type", "document").execute()
    file_titles = sorted({row.get("file_title") for row in (result.data or []) if row.get("file_title")})
    reports = [{"file_title": file_title} for file_title in file_titles]
    logger.info("Listed available reports from document_tree_nodes. total_reports=%s", len(reports))
    return {"total_reports": len(reports), "reports": reports}


@tool
def retrieve_embedded_financial_report_info(
    query: str,
    file_title: str = "",
    top_k: int = 5,
    filename: str = "",
) -> dict:
    """
    Retrieve relevant report content by:
    1) finding all document nodes
    2) selecting the most relevant document node for the query
    3) traversing that tree with traverse_document_tree_nodes
    4) scoring traversed nodes and returning top matches
    """
    logger.info(
        "Retrieving embedded report info. file_title=%s filename=%s top_k=%s query_preview=%s",
        file_title,
        filename,
        top_k,
        query[:120],
    )
    supabase = _get_supabase_client()
    query_embedding = _embed_query(query)
    selected_title = file_title or filename

    documents_query = (
        supabase.table("document_tree_nodes")
        .select("id, parent_id, node_type, file_title, title, text, depth, metadata, embedding")
        .eq("node_type", "document")
    )
    if selected_title:
        documents_query = documents_query.eq("file_title", selected_title)
    document_nodes = documents_query.execute().data or []
    if not document_nodes:
        logger.warning("No document nodes found for retrieval. file_title=%s", selected_title)
        return {"error": "No document nodes found in document_tree_nodes."}

    best_document = None
    best_document_score = -1.0
    for document_node in document_nodes:
        document_embedding = _parse_embedding(document_node.get("embedding"))
        if not document_embedding:
            continue
        score = _cosine_similarity(query_embedding, document_embedding)
        if score > best_document_score:
            best_document = document_node
            best_document_score = score

    if not best_document:
        logger.warning("No document nodes had valid embeddings.")
        return {"error": "No document nodes had valid embeddings."}

    selected_file_title = best_document.get("file_title") or ""
    logger.info(
        "Selected document node for traversal. node_id=%s file_title=%s score=%.4f",
        best_document["id"],
        selected_file_title,
        best_document_score,
    )

    traversal_result = supabase.rpc(
        "traverse_document_tree_nodes",
        {"start_node_id": best_document["id"], "mode": "down", "max_hops": 64},
    ).execute()
    traversed_nodes = traversal_result.data or []
    if not traversed_nodes:
        logger.warning("Traversal returned no nodes. start_node_id=%s", best_document["id"])
        return {"error": "Traversal returned no nodes for the selected document."}

    all_nodes_result = (
        supabase.table("document_tree_nodes")
        .select("id, parent_id, node_type, file_title, title, text, depth, metadata, embedding")
        .eq("file_title", selected_file_title)
        .execute()
    )
    all_nodes = all_nodes_result.data or []
    if not all_nodes:
        logger.warning("No nodes found for selected file_title=%s", selected_file_title)
        return {"error": f"No nodes found for selected file_title: {selected_file_title}"}

    nodes_by_id = {node["id"]: node for node in all_nodes}
    traversal_lookup = {node["id"]: node for node in traversed_nodes}
    scored_matches = []

    for traversed in traversed_nodes:
        source_node = nodes_by_id.get(traversed["id"])
        if not source_node:
            continue
        node_type = _node_type(source_node)
        if node_type == "document":
            continue
        node_embedding = _parse_embedding(source_node.get("embedding"))
        if not node_embedding:
            continue
        similarity = _cosine_similarity(query_embedding, node_embedding)
        scored_matches.append(
            {
                "title": source_node.get("title"),
                "file_title": source_node.get("file_title"),
                "text": source_node.get("text"),
                "lineage": _build_node_lineage(traversal_lookup, source_node["id"]),
                "metadata": source_node.get("metadata"),
                "depth": source_node.get("depth"),
                "node_type": node_type,
                "score": round(similarity, 4),
            }
        )

    scored_matches.sort(key=lambda item: item["score"], reverse=True)
    returned_count = max(1, int(top_k))
    logger.info(
        "Retrieved embedded report matches via traversal. file_title=%s traversed_nodes=%s candidates=%s returned=%s",
        selected_file_title,
        len(traversed_nodes),
        len(scored_matches),
        returned_count,
    )
    return {
        "selected_document_node": {
            "id": best_document["id"],
            "title": best_document.get("title"),
            "file_title": selected_file_title,
            "score": round(best_document_score, 4),
        },
        "query": query,
        "matches": scored_matches[:returned_count],
    }
