import fitz
from openai import OpenAI
import os
import random
import time
from dotenv import load_dotenv
from supabase import create_client, Client
import json
import uuid
from langchain_text_splitters import RecursiveCharacterTextSplitter


load_dotenv()

NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")
SUPABASE_URL = "https://ctublgctoyuwuxwanujg.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MODEL = os.getenv("MODEL_NAME")

BATCH_SIZE = 10

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
SECTION_CHUNK_SIZE = 12000
SECTION_CHUNK_OVERLAP = 800
MAX_LLM_RETRIES = 3
NODE_SUMMARY_CHAR_LIMIT = 4000
RATE_LIMIT_BASE_DELAY_SECONDS = 15
BATCH_SIZE = 50  # insert in batches
SEMANTIC_SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", "},", "],", ", ", " ", ""]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
client = OpenAI(
  api_key=NVIDIA_API_KEY,
  base_url="https://integrate.api.nvidia.com/v1"
)


def chat_json_completion(prompt):
    last_error = None

    for attempt in range(1, MAX_LLM_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
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
            print(
                f"LLM call failed on attempt {attempt}/{MAX_LLM_RETRIES}: {error}. "
                f"Retrying in {delay_seconds:.1f}s..."
            )
            time.sleep(delay_seconds)

    raise last_error


def chat_text_completion(prompt):
    last_error = None

    for attempt in range(1, MAX_LLM_RETRIES + 1):
        try:
            response = client.chat.completions.create(
                model=MODEL,
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
            print(
                f"LLM call failed on attempt {attempt}/{MAX_LLM_RETRIES}: {error}. "
                f"Retrying in {delay_seconds:.1f}s..."
            )
            time.sleep(delay_seconds)

    raise last_error

# --- NEW: FIND THE TOC PAGE ---


def find_toc_page(doc):
    """Scans the beginning of the PDF to find which page is the Table of Contents."""
    # We usually only need to check the first 5 pages
    scan_limit = min(5, len(doc))
    preview_text = ""
    for i in range(scan_limit):
        preview_text += f"--- PAGE {i+1} ---\n{doc[i].get_text()}\n\n"

    prompt = """
    Analyze the following pages from an SEC filing. 
    Identify the page number that contains the primary 'Table of Contents' list.
    Return a JSON object: {"toc_page": int}
    """
    
    res = chat_json_completion(f"{prompt}\n\n{preview_text}")
    return res.get("toc_page", 2) # Default to 2 if unsure

# --- UPDATED: ORCHESTRATOR (PASS IN ONLY TOC TEXT) ---
def create_section_map(toc_text):
    prompt = f"""
    You are a document architect analyzing the following Table of Contents text from an NVIDIA 10-K.
    
    TOC TEXT:
    {toc_text}

    RULES:
    1. Identify 'Part', 'Item Number', 'Title', and 'Start Page'.
    2. Calculate 'end_page' for each item. The 'end_page' is the 'start_page' of the next sequential item.
    3. If multiple items share the same page (e.g., Item 1B and 1C), 'start_page' and 'end_page' will be the same.
    4. Ignore the 'Signatures' section.
    
    RETURN FORMAT:
    A JSON object:
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
    return chat_json_completion(prompt)

section_splitter = RecursiveCharacterTextSplitter(
    chunk_size=SECTION_CHUNK_SIZE,
    chunk_overlap=SECTION_CHUNK_OVERLAP,
    separators=SEMANTIC_SEPARATORS
)


def process_section_chunk_to_rag_format(section_title, section_text):
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
    return chat_text_completion(f"{prompt}\n\nContent:\n{section_text}")


def process_section_to_rag_format(section_title, section_text):
    section_chunks = section_splitter.split_text(section_text)

    if len(section_chunks) <= 1:
        return process_section_chunk_to_rag_format(section_title, section_text)

    merged_content = []

    for index, chunk in enumerate(section_chunks, start=1):
        chunk_title = f"{section_title} (part {index}/{len(section_chunks)})"
        print(f"  Processing subsection {index}/{len(section_chunks)} for {section_title}...")
        partial_result = process_section_chunk_to_rag_format(chunk_title, chunk)
        if partial_result.strip():
            merged_content.append(partial_result.strip())

    return "\n\n".join(merged_content)

def get_pdf_text_range(doc, start_page, end_page):
    text = ""
    for i in range(start_page - 1, min(end_page, len(doc))):
        text += f"{doc[i].get_text()}\n"
    return text

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=15000, 
    chunk_overlap=1000,
    separators=["\n\n", "\n", " ", ""]
)

pdf_path = "nvidia_10k.pdf"
filename = os.path.basename(pdf_path)

doc = fitz.open(pdf_path)

# 1. Locate TOC Page
print("Locating Table of Contents...")
toc_page_num = find_toc_page(doc)

print(f"Identified TOC on Page {toc_page_num}")

# 2. Extract only the TOC page text
toc_text = doc[toc_page_num - 1].get_text()

# 3. Create Section Map using only TOC text
print(f"Parsing TOC from Page {toc_page_num}...")
section_map = create_section_map(toc_text)

print("Section Map:")
print(json.dumps(section_map, indent=2))

final_rag_payload = []

# 4. Iterate over mapped sections
for item in section_map['sections']:
    title = f"{item['item']}: {item['title']}"
    start, end = item['start_page'], item['end_page']
    
    print(f"Processing {title} (Pages {start}-{end})...")
    raw_section_text = get_pdf_text_range(doc, start, end)
    print(f"Extracted {len(raw_section_text)} characters for {title}")
    
    processed_content = {
        "title": title,
        "content": process_section_to_rag_format(title, raw_section_text),
        "metadata": {
            "part": item['part'],
            "item": item['item'],
            "title": title,
            "page_range": f"{start}-{end}",
            "filename": filename,
        },
    }

    final_rag_payload.append(processed_content)


# Use a smaller splitter for the actual vector embeddings (leaf nodes)
leaf_splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=150,
    separators=SEMANTIC_SEPARATORS
)

def stringify_content(content):
    if isinstance(content, (dict, list)):
        return json.dumps(content, indent=2)
    return str(content)


def compact_text(text, limit=NODE_SUMMARY_CHAR_LIMIT):
    normalized = " ".join(str(text).split())
    if len(normalized) <= limit:
        return normalized
    return normalized[:limit].rstrip() + " ..."


def build_tree_nodes(payload, source_filename):
    document_id = str(uuid.uuid4())
    root_id = str(uuid.uuid4())
    section_titles = [item["title"] for item in payload]
    root_text = "Document outline:\n" + "\n".join(section_titles)

    nodes = [
        {
            "id": root_id,
            "document_id": document_id,
            "parent_id": None,
            "node_type": "document",
            "depth": 0,
            "sequence": 0,
            "title": source_filename,
            "filename": source_filename,
            "text": root_text,
            "embedding_text": build_embedding_text(source_filename, source_filename, compact_text(root_text)),
            "metadata": {
                "title": source_filename,
                "filename": source_filename,
                "section_count": len(payload),
            },
        }
    ]

    for section_index, item in enumerate(payload):
        section_id = str(uuid.uuid4())
        section_text = stringify_content(item.get("content", ""))
        section_preview = compact_text(section_text)
        section_metadata = {
            **item.get("metadata", {}),
            "title": item["title"],
            "filename": item["metadata"].get("filename", source_filename),
        }

        nodes.append({
            "id": section_id,
            "document_id": document_id,
            "parent_id": root_id,
            "node_type": "section",
            "depth": 1,
            "sequence": section_index,
            "title": item["title"],
            "filename": item["metadata"].get("filename", source_filename),
            "text": section_text,
            "embedding_text": build_embedding_text(
                item["title"],
                item["metadata"].get("filename", source_filename),
                f"Section summary: {section_preview}",
            ),
            "metadata": section_metadata,
        })

        leaf_chunks = leaf_splitter.split_text(section_text)
        for chunk_index, chunk in enumerate(leaf_chunks):
            nodes.append({
                "id": str(uuid.uuid4()),
                "document_id": document_id,
                "parent_id": section_id,
                "node_type": "chunk",
                "depth": 2,
                "sequence": chunk_index,
                "title": item["title"],
                "filename": item["metadata"].get("filename", source_filename),
                "text": chunk,
                "embedding_text": build_embedding_text(
                    item["title"],
                    item["metadata"].get("filename", source_filename),
                    chunk,
                ),
                "metadata": {
                    **section_metadata,
                    "title": item["title"],
                    "filename": item["metadata"].get("filename", source_filename),
                    "chunk_index": chunk_index,
                },
            })

    return nodes


def process_and_index_payload(payload, supabase_client):
    nodes_for_indexing = build_tree_nodes(payload, filename)
    print(f"Prepared {len(nodes_for_indexing)} tree nodes. Starting indexer...")
    index_nodes(nodes_for_indexing, supabase_client)

def index_nodes(nodes, supabase):
    batch_rows = []
    batch_inputs = []

    def flush_batch():
        nonlocal batch_rows, batch_inputs
        if not batch_rows:
            return

        embeddings = embed_batch(batch_inputs)

        for row, embedding in zip(batch_rows, embeddings):
            row["embedding"] = embedding

        supabase.table("document_tree_nodes").insert(batch_rows).execute()
        batch_rows = []
        batch_inputs = []

    for node in nodes:
        try:
            batch_rows.append({
                "id": node["id"],
                "document_id": node["document_id"],
                "parent_id": node["parent_id"],
                "node_type": node["node_type"],
                "title": node["title"],
                "filename": node["filename"],
                "text": node["text"],
                "depth": node["depth"],
                "sequence": node["sequence"],
                "metadata": node["metadata"],
            })
            batch_inputs.append(node["embedding_text"])

            if len(batch_rows) >= BATCH_SIZE:
                flush_batch()
        except Exception as e:
            print(f"Error during embedding/indexing for {node['title']}: {e}")
            continue

    flush_batch()
    print("Indexing Complete.")


import uuid

# Configuration
BATCH_SIZE = 10  # Adjust based on Supabase/NVIDIA API limits


def chunk_text(text, chunk_size=800, overlap=150):
    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def build_embedding_text(title, filename, text):
    return f"Title: {title}\nFilename: {filename}\nText: {text}"



def embed_batch(texts):

    print(f"Embedding batch of {len(texts)} chunks...")
    # skip if text is empty
    texts = [t for t in texts if t.strip()]

    response = client.embeddings.create(
        model="baai/bge-m3",
        input=texts,
        encoding_format="float",
        extra_body={"truncate": "NONE"}
    )

    return [d.embedding for d in response.data]


# 2. Index the results
process_and_index_payload(final_rag_payload, supabase)

def embed_query(query):

    response = client.embeddings.create(
        model="baai/bge-m3",
        input=[query],
        encoding_format="float"
    )

    return response.data[0].embedding

def fetch_node(node_id):
    result = supabase.table("document_tree_nodes").select(
        "id, document_id, parent_id, node_type, title, filename, text, depth, sequence, metadata"
    ).eq("id", node_id).limit(1).execute()
    return result.data[0] if result.data else None


def fetch_lineage(node_id):
    lineage = []
    current = fetch_node(node_id)

    while current:
        lineage.append(current)
        parent_id = current.get("parent_id")
        if not parent_id:
            break
        current = fetch_node(parent_id)

    lineage.reverse()
    return lineage

# 1. Define the Evaluation Questions
eval_queries = [
    "What are NVIDIA's main revenue segments?",
    "What are the specific risk factors regarding the supply chain and manufacturing?",
    "What was the net income for fiscal year 2024?",
    "How does NVIDIA manage cybersecurity risks?",
    "What is the impact of US export controls on Data Center revenue?"
]

def retrieve_chunks(query, limit=3):
    """
    Retrieve the best chunk matches and their document/section lineage.
    """
    query_embedding = embed_batch([query])[0]
    
    res = supabase.rpc("match_document_tree_nodes", {
        "query_embedding": query_embedding,
        "match_threshold": 0.1,
        "match_count": limit,
        "match_depth": 2,
    }).execute()

    results = []
    for match in res.data:
        match["lineage"] = fetch_lineage(match["id"])
        results.append(match)

    return results

def evaluate_relevance(query, context):
    """
    LLM as Judge: Checks if the retrieved text is actually useful for the query.
    """
    prompt = f"""
    You are a Relevance Auditor. 
    QUERY: {query}
    RETRIVED TEXT: {context}

    TASK:
    Does the RETRIEVED TEXT contain information that helps answer the QUERY?
    Return a JSON object: 
    {{
      "is_relevant": boolean,
      "score": int (1-10),
      "reasoning": "short explanation"
    }}
    """
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

# --- RUN EVALUATION ---
for query in eval_queries:
    print(f"\n🔍 EVALUATING QUERY: {query}")
    results = retrieve_chunks(query)

    for i, r in enumerate(results):
        time.sleep(30)  # To avoid hitting rate limits
        # 1. Show the retrieval data
        lineage_titles = " > ".join(node["title"] for node in r.get("lineage", []))
        print(f"\n  Chunk {i+1} | Title: {r['title']} | Similarity: {r.get('similarity', 'N/A'):.4f}")
        print(f"  Lineage: {lineage_titles}")
        print(f"  Filename: {r.get('filename', 'N/A')}")
        
        # 2. Run the Judge
        judgment = evaluate_relevance(query, r['text'])
        
        # 3. Print the Verdict
        status = "✅ RELEVANT" if judgment['is_relevant'] else "❌ IRRELEVANT"
        print(f"  Verdict: {status} (Score: {judgment['score']}/10)")
        print(f"  Reason: {judgment['reasoning']}")
        print(f"  Snippet: {r['text'][:150]}...")
