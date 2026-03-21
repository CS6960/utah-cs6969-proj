from __future__ import annotations

import json
import math
import os
import random
import tempfile
import time
import uuid
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

import fitz
from dotenv import load_dotenv
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.tools import tool
from openai import OpenAI


load_dotenv()

API_KEY = os.getenv("API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME", "meta/llama-3.1-70b-instruct")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "baai/bge-m3")
SECTION_CHUNK_SIZE = 12000
SECTION_CHUNK_OVERLAP = 800
MAX_LLM_RETRIES = 3
NODE_SUMMARY_CHAR_LIMIT = 4000
RATE_LIMIT_BASE_DELAY_SECONDS = 15
SEMANTIC_SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "},", "],", ", ", " ", ""]

REPORT_STORE: dict[str, dict[str, Any]] = {}
EMBEDDED_REPORT_STORE: dict[str, dict[str, Any]] = {}

section_splitter = RecursiveCharacterTextSplitter(
    chunk_size=SECTION_CHUNK_SIZE,
    chunk_overlap=SECTION_CHUNK_OVERLAP,
    separators=SEMANTIC_SEPARATORS,
)

leaf_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=150,
    separators=SEMANTIC_SEPARATORS,
)


def _get_client() -> OpenAI:
    if not API_KEY:
        raise ValueError("API_KEY is not configured.")

    return OpenAI(
        api_key=API_KEY,
        base_url="https://integrate.api.nvidia.com/v1",
    )


def _chat_json_completion(prompt: str) -> dict[str, Any]:
    client = _get_client()
    last_error = None

    for attempt in range(1, MAX_LLM_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except Exception as error:
            last_error = error
            if attempt == MAX_LLM_RETRIES:
                raise
            error_text = str(error)
            is_rate_limit = "429" in error_text or "Too Many Requests" in error_text
            base_delay = RATE_LIMIT_BASE_DELAY_SECONDS if is_rate_limit else 2
            delay_seconds = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1.5)
            time.sleep(delay_seconds)

    raise last_error


def _chat_text_completion(prompt: str) -> str:
    client = _get_client()
    last_error = None

    for attempt in range(1, MAX_LLM_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.choices[0].message.content
            return content.strip() if content else ""
        except Exception as error:
            last_error = error
            if attempt == MAX_LLM_RETRIES:
                raise
            error_text = str(error)
            is_rate_limit = "429" in error_text or "Too Many Requests" in error_text
            base_delay = RATE_LIMIT_BASE_DELAY_SECONDS if is_rate_limit else 2
            delay_seconds = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1.5)
            time.sleep(delay_seconds)

    raise last_error


def _download_pdf_bytes(pdf_url: str) -> bytes:
    with urlopen(pdf_url) as response:
        status = getattr(response, "status", 200)
        if status != 200:
            raise ValueError(f"Unable to download PDF. HTTP status {status}.")
        return response.read()


def _extract_page_texts(pdf_bytes: bytes) -> list[str]:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(pdf_bytes)
        temp_path = temp_file.name

    try:
        doc = fitz.open(temp_path)
        try:
            return [doc[index].get_text() for index in range(len(doc))]
        finally:
            doc.close()
    finally:
        try:
            os.unlink(temp_path)
        except FileNotFoundError:
            pass


def _get_report(report_id: str) -> dict[str, Any]:
    report = REPORT_STORE.get(report_id)
    if not report:
        raise ValueError(f"Unknown report_id: {report_id}")
    return report


def _filename_from_pdf_url(pdf_url: str) -> str:
    parsed = urlparse(pdf_url)
    filename = os.path.basename(parsed.path)
    return filename or "financial_report.pdf"


def _find_toc_page_from_pages(page_texts: list[str]) -> int:
    scan_limit = min(5, len(page_texts))
    preview_text = ""

    for index in range(scan_limit):
        preview_text += f"--- PAGE {index + 1} ---\n{page_texts[index]}\n\n"

    prompt = """
    Analyze the following pages from an SEC filing.
    Identify the page number that contains the primary Table of Contents.
    Return a JSON object: {"toc_page": int}
    """

    payload = _chat_json_completion(f"{prompt}\n\n{preview_text}")
    return int(payload.get("toc_page", 2))


def _create_section_map_from_toc(toc_text: str) -> dict[str, Any]:
    prompt = f"""
    You are a document architect analyzing the following Table of Contents text from an SEC filing.

    TOC TEXT:
    {toc_text}

    RULES:
    1. Identify Part, Item Number, Title, and Start Page.
    2. Calculate end_page for each item. The end_page is the start_page of the next sequential item.
    3. If multiple items share the same page, start_page and end_page can be the same.
    4. Ignore Signatures and other appendix-style sections unless they are clearly numbered filing items.

    RETURN FORMAT:
    {{
      "sections": [
        {{
          "part": "Part I",
          "item": "Item 1",
          "title": "Business",
          "start_page": 4,
          "end_page": 13
        }}
      ]
    }}
    """

    return _chat_json_completion(prompt)


def _process_section_chunk_to_rag_format(section_title: str, section_text: str) -> str:
    prompt = f"""
    You are a data engineer processing the section: {section_title}.
    Return one plain text string only.

    RULES:
    1. Preserve the original facts and wording as closely as possible.
    2. Do not return JSON, Python literals, dicts, arrays, or markdown code fences.
    3. Convert tables into readable row-wise plain text.
    4. For each table row, concatenate header-value pairs into one line.
    5. Return only the final string content for this section.
    """

    return _chat_text_completion(f"{prompt}\n\nContent:\n{section_text}")


def _process_section_to_rag_format(section_title: str, section_text: str) -> str:
    section_chunks = _chunk_text(
        section_text,
        chunk_size=SECTION_CHUNK_SIZE,
        overlap=SECTION_CHUNK_OVERLAP,
    )

    if len(section_chunks) <= 1:
        return _process_section_chunk_to_rag_format(section_title, section_text)

    merged_content = []

    for index, chunk in enumerate(section_chunks, start=1):
        partial_result = _process_section_chunk_to_rag_format(
            f"{section_title} (part {index}/{len(section_chunks)})",
            chunk,
        )
        if partial_result.strip():
            merged_content.append(partial_result.strip())

    return "\n\n".join(merged_content)


def _get_page_range_text(page_texts: list[str], start_page: int, end_page: int) -> str:
    text_parts = []

    for index in range(start_page - 1, min(end_page, len(page_texts))):
        text_parts.append(page_texts[index])

    return "\n".join(text_parts)


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    splitter = leaf_splitter

    if chunk_size == SECTION_CHUNK_SIZE and overlap == SECTION_CHUNK_OVERLAP:
        splitter = section_splitter

    return [chunk for chunk in splitter.split_text(text) if chunk.strip()]


def _build_embedding_text(title: str, filename: str, text: str) -> str:
    return f"Title: {title}\nFilename: {filename}\nText: {text}"


def _embed_batch(texts: list[str]) -> list[list[float]]:
    clean_texts = [text for text in texts if text.strip()]
    if not clean_texts:
        return []

    client = _get_client()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=clean_texts,
        encoding_format="float",
        extra_body={"truncate": "NONE"},
    )

    return [item.embedding for item in response.data]


def _cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    dot_product = sum(a * b for a, b in zip(vector_a, vector_b))
    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))

    if not norm_a or not norm_b:
        return 0.0

    return dot_product / (norm_a * norm_b)


def _stringify_content(content: Any) -> str:
    if isinstance(content, (dict, list)):
        return json.dumps(content, indent=2)
    return str(content)


def _compact_text(text: str, limit: int = NODE_SUMMARY_CHAR_LIMIT) -> str:
    normalized = " ".join(str(text).split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + " ..."


def _build_report_tree_nodes(report_id: str, filename: str, payload: list[dict[str, Any]]) -> list[dict[str, Any]]:
    root_id = str(uuid.uuid4())
    section_titles = [item["title"] for item in payload]
    root_text = "Document outline:\n" + "\n".join(section_titles)
    nodes = [
        {
            "id": root_id,
            "report_id": report_id,
            "parent_id": None,
            "node_type": "document",
            "depth": 0,
            "title": filename,
            "filename": filename,
            "text": root_text,
            "embedding_text": _build_embedding_text(filename, filename, _compact_text(root_text)),
            "metadata": {"title": filename, "filename": filename, "section_count": len(payload)},
        }
    ]

    for section in payload:
        section_id = str(uuid.uuid4())
        section_text = _stringify_content(section.get("content", ""))
        section_preview = _compact_text(section_text)
        section_metadata = {**section.get("metadata", {}), "title": section["title"], "filename": filename}
        nodes.append(
            {
                "id": section_id,
                "report_id": report_id,
                "parent_id": root_id,
                "node_type": "section",
                "depth": 1,
                "title": section["title"],
                "filename": filename,
                "text": section_text,
                "embedding_text": _build_embedding_text(
                    section["title"],
                    filename,
                    f"Section summary: {section_preview}",
                ),
                "metadata": section_metadata,
            }
        )

        chunks = _chunk_text(section_text)
        embedding_texts = [_build_embedding_text(section["title"], filename, chunk) for chunk in chunks]
        embeddings = _embed_batch(embedding_texts)

        for chunk_index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            nodes.append(
                {
                    "id": str(uuid.uuid4()),
                    "report_id": report_id,
                    "parent_id": section_id,
                    "node_type": "chunk",
                    "depth": 2,
                    "title": section["title"],
                    "filename": filename,
                    "text": chunk,
                    "embedding_text": _build_embedding_text(section["title"], filename, chunk),
                    "embedding": embedding,
                    "metadata": {**section_metadata, "title": section["title"], "filename": filename, "chunk_index": chunk_index},
                }
            )

    return nodes


def _build_node_lineage(node_lookup: dict[str, dict[str, Any]], node_id: str) -> list[dict[str, Any]]:
    lineage = []
    current = node_lookup.get(node_id)

    while current:
        lineage.append(
            {
                "id": current["id"],
                "node_type": current["node_type"],
                "title": current["title"],
                "filename": current["filename"],
                "depth": current["depth"],
                "metadata": current["metadata"],
            }
        )
        parent_id = current.get("parent_id")
        current = node_lookup.get(parent_id) if parent_id else None

    lineage.reverse()
    return lineage


@tool
def download_financial_report(pdf_url: str) -> dict:
    """
    Download a financial report PDF from a URL, extract page text, and store it for later processing.
    """
    report_id = str(uuid.uuid4())
    pdf_bytes = _download_pdf_bytes(pdf_url)
    page_texts = _extract_page_texts(pdf_bytes)
    filename = _filename_from_pdf_url(pdf_url)

    REPORT_STORE[report_id] = {
        "pdf_url": pdf_url,
        "filename": filename,
        "page_texts": page_texts,
        "page_count": len(page_texts),
        "toc_page": None,
        "toc_text": None,
        "section_map": None,
        "final_rag_payload": None,
    }

    return {
        "report_id": report_id,
        "pdf_url": pdf_url,
        "filename": filename,
        "page_count": len(page_texts),
    }


@tool
def find_financial_report_table_of_contents(report_id: str) -> dict:
    """
    Find the table of contents page for a previously downloaded financial report.
    """
    report = _get_report(report_id)
    toc_page = _find_toc_page_from_pages(report["page_texts"])
    toc_text = report["page_texts"][toc_page - 1] if toc_page - 1 < len(report["page_texts"]) else ""

    report["toc_page"] = toc_page
    report["toc_text"] = toc_text

    return {
        "report_id": report_id,
        "toc_page": toc_page,
        "toc_preview": toc_text[:2000],
    }


@tool
def create_financial_report_section_map(report_id: str) -> dict:
    """
    Create a section map for a downloaded financial report using its detected table of contents.
    """
    report = _get_report(report_id)

    if not report.get("toc_text"):
        raise ValueError("Table of contents not found yet. Call find_financial_report_table_of_contents first.")

    section_map = _create_section_map_from_toc(report["toc_text"])
    report["section_map"] = section_map

    return {
        "report_id": report_id,
        "section_count": len(section_map.get("sections", [])),
        "section_map": section_map,
    }


@tool
def embed_financial_report_content(report_id: str) -> dict:
    """
    Process section content into a final RAG payload, embed the content, and store the embedded chunks.
    """
    report = _get_report(report_id)
    filename = report["filename"]

    if not report.get("section_map"):
        raise ValueError("Section map not found yet. Call create_financial_report_section_map first.")

    final_rag_payload = []
    for section in report["section_map"].get("sections", []):
        title = f"{section['item']}: {section['title']}"
        start_page = int(section["start_page"])
        end_page = int(section["end_page"])
        raw_section_text = _get_page_range_text(report["page_texts"], start_page, end_page)
        processed_content = {
            "title": title,
            "content": _process_section_to_rag_format(title, raw_section_text),
            "metadata": {
                "part": section["part"],
                "item": section["item"],
                "title": title,
                "page_range": f"{start_page}-{end_page}",
                "filename": filename,
            },
        }
        final_rag_payload.append(processed_content)

    report["final_rag_payload"] = final_rag_payload
    tree_nodes = _build_report_tree_nodes(report_id, filename, final_rag_payload)
    node_lookup = {node["id"]: node for node in tree_nodes}
    EMBEDDED_REPORT_STORE[report_id] = {
        "nodes": tree_nodes,
        "node_lookup": node_lookup,
    }

    embedded_chunk_count = sum(1 for node in tree_nodes if node["node_type"] == "chunk")

    return {
        "report_id": report_id,
        "filename": filename,
        "payload_section_count": len(final_rag_payload),
        "embedded_chunk_count": embedded_chunk_count,
        "final_rag_payload": final_rag_payload,
    }


@tool
def retrieve_embedded_financial_report_info(report_id: str, query: str, top_k: int = 5) -> dict:
    """
    Retrieve the most relevant embedded chunks from a previously embedded financial report.
    """
    embedded_report = EMBEDDED_REPORT_STORE.get(report_id)
    if not embedded_report:
        return {"error": f"No embedded report found for report_id: {report_id}"}

    query_embedding = _embed_batch([query])
    if not query_embedding:
        return {"error": "Unable to embed the retrieval query."}

    embedded_chunks = [
        node for node in embedded_report["nodes"]
        if node["node_type"] == "chunk" and node.get("embedding") is not None
    ]
    scored_chunks = []

    for chunk in embedded_chunks:
        score = _cosine_similarity(query_embedding[0], chunk["embedding"])
        scored_chunks.append(
            {
                "title": chunk["title"],
                "filename": chunk["filename"],
                "text": chunk["text"],
                "lineage": _build_node_lineage(embedded_report["node_lookup"], chunk["id"]),
                "metadata": chunk["metadata"],
                "score": round(score, 4),
            }
        )

    scored_chunks.sort(key=lambda item: item["score"], reverse=True)
    return {
        "report_id": report_id,
        "query": query,
        "matches": scored_chunks[: max(1, int(top_k))],
    }
