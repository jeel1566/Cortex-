"""
ingest_slack.py — Full ingestion compiler for Cortex Phase 1.

Pipeline:
  1. Load & filter messages from messages.csv (PII-redacted, user-mapped)
  2. Split into sentences
  3. Classify sentences (CONDITION / PRESCRIPTION / PROCEDURE / EXCEPTION / OUTCOME)
  4. Cluster sentences into decision units
  5. Synthesize one markdown knowledge page per cluster (+ validate)
  6. Save pages to data/tenants/default/os/pages/
  7. Build graph adjacency list from page primary/secondary links -> adjacency.json
  8. Embed each page and populate the NumPy vector index -> vector_index.json

Usage:
    python phase-1/ingest_slack.py [--max-messages N] [--batch-size N]
"""

import os
import sys
import re
import json
import time
import datetime
import argparse

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(BASE_DIR, "phase-1"))
sys.path.append(os.path.join(BASE_DIR, "phase-1", "app"))

# Also allow running from within phase-1/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from app.ingestion.pipeline import load_and_filter_csv, split_into_sentences
from app.ingestion.classifier import classify_sentences
from app.ingestion.clusterer import cluster_sentences
from app.ingestion.synthesizer import synthesize_page
from app.ingestion.validation import validate_page
from app.llm.embedding import encode
from app.storage.hnsw_index import NumPyVectorIndex
from app.storage.graph import CortexGraph


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PHASE1_DIR  = os.path.abspath(os.path.dirname(__file__))
DATA_DIR    = os.path.join(PHASE1_DIR, "data")
CSV_PATH    = os.path.join(DATA_DIR, "messages.csv")
USERS_CSV   = os.path.join(DATA_DIR, "users.csv")
TENANT_DIR  = os.path.join(DATA_DIR, "tenants", "default")
PAGES_DIR   = os.path.join(TENANT_DIR, "os", "pages")
GRAPH_DIR   = os.path.join(TENANT_DIR, "os", "graph")
INDEX_PATH  = os.path.join(TENANT_DIR, "os", "vector_index.json")
ADJ_PATH    = os.path.join(GRAPH_DIR, "adjacency.json")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def extract_yaml_field(content: str, field: str):
    """Pull a scalar or list value from YAML frontmatter."""
    pattern = rf"^{field}:\s*(.+)$"
    m = re.search(pattern, content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return None

def extract_yaml_list(content: str, field: str):
    """Extract a YAML list like:
        primary_links:
          - page_001
          - page_002
    """
    block_pattern = rf"^{field}:\s*\n((?:\s+- .+\n?)*)"
    m = re.search(block_pattern, content, re.MULTILINE)
    if m:
        items = re.findall(r"-\s+(\S+)", m.group(1))
        return items
    # inline list: primary_links: [page_001, page_002]
    inline = extract_yaml_field(content, field)
    if inline and inline.startswith("["):
        items = re.findall(r"[\w_]+", inline)
        return items
    return []

def extract_secondary_links(content: str):
    """Extract secondary_links: [{condition, page}] from YAML."""
    links = []
    # Match: - condition: "..."
    #          page: page_xxx
    pattern = r'- condition:\s*["\']?([^"\'\\n]+)["\']?\s*\n\s*page:\s*(\S+)'
    for m in re.finditer(pattern, content, re.MULTILINE):
        links.append({"condition": m.group(1).strip(), "page": m.group(2).strip()})
    return links

def ensure_dirs():
    for d in [PAGES_DIR, GRAPH_DIR]:
        os.makedirs(d, exist_ok=True)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def run(max_messages: int, batch_size: int):
    t_total = time.time()
    ensure_dirs()

    # ── Step 1: Load & filter ──────────────────────────────────────────────
    print(f"\n[1/7] Loading messages from {CSV_PATH} ...")
    messages = load_and_filter_csv(CSV_PATH)
    print(f"      Loaded {len(messages)} messages after filtering.")
    if max_messages:
        messages = messages[:max_messages]
        print(f"      Capped at {len(messages)} messages (--max-messages {max_messages}).")

    # ── Step 2: Sentences ──────────────────────────────────────────────────
    print(f"\n[2/7] Splitting into sentences ...")
    sentence_records = []
    for msg in messages:
        for s in split_into_sentences(msg["text"]):
            sentence_records.append({
                "text": s,
                "metadata": {
                    "user":      msg["user"],
                    "channel":   msg["channel"],
                    "timestamp": msg["timestamp"],
                    "source_id": msg["source_id"],
                }
            })
    print(f"      Generated {len(sentence_records)} sentences.")

    # ── Step 3: Classify ───────────────────────────────────────────────────
    print(f"\n[3/7] Classifying sentences (batch_size={batch_size}) ...")
    texts = [r["text"] for r in sentence_records]
    classified_types = []
    num_batches = -(-len(texts) // batch_size)  # ceil div
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        print(f"      Batch {i // batch_size + 1}/{num_batches} ({len(batch)} sentences)...")
        classified_types.extend(classify_sentences(batch))
    for r, t in zip(sentence_records, classified_types):
        r["type"] = t
    print(f"      Classification complete.")

    # ── Step 4: Cluster ────────────────────────────────────────────────────
    print(f"\n[4/7] Clustering sentences into decision units ...")
    clusters = cluster_sentences(sentence_records, similarity_threshold=0.68)
    print(f"      Formed {len(clusters)} clusters.")

    # ── Step 5 & 6: Synthesize, validate, save pages ──────────────────────
    print(f"\n[5/7] Synthesizing and validating knowledge pages ...")
    vector_index = NumPyVectorIndex(index_path=INDEX_PATH, dim=384)
    graph = CortexGraph(adjacency_path=ADJ_PATH)

    pages_meta = []
    for idx, cluster in enumerate(clusters):
        page_num  = idx + 1
        page_id   = f"page_{page_num:03d}"
        sources   = [item["text"] for item in cluster]

        print(f"  [{page_num:3d}/{len(clusters)}] Synthesizing {page_id} ({len(cluster)} sentences)...")
        attempts = 0
        page_content = ""
        validation   = {}
        passed       = False

        while attempts < 3 and not passed:
            attempts += 1
            page_content = synthesize_page(page_num, cluster)
            validation   = validate_page(sources, page_content)
            passed       = validation.get("validation_passed", False)
            if not passed:
                print(f"           Validation failed (attempt {attempts}): {validation.get('reason','')}")

        status = "APPROVED" if passed else "DRAFT"

        # Inject synthesis_validation block into YAML header
        val_block = (
            f"synthesis_validation:\n"
            f"  proposition_coverage: {validation.get('proposition_coverage', 0.0):.2f}\n"
            f"  hallucination_rate: {validation.get('hallucination_rate', 1.0):.2f}\n"
            f"  completeness_score: {validation.get('completeness_score', 1)}\n"
            f"  validation_passed: {str(passed).lower()}\n"
            f"  validated_at: {datetime.datetime.utcnow().isoformat()}Z\n"
        )
        if page_content.startswith("---"):
            close = page_content.find("---", 3)
            if close != -1:
                page_content = (
                    page_content[:close]
                    + val_block
                    + page_content[close:]
                )

        # Save page file
        page_path = os.path.join(PAGES_DIR, f"{page_id}.md")
        with open(page_path, "w", encoding="utf-8") as f:
            f.write(page_content)

        pages_meta.append({
            "page_id":    page_id,
            "content":    page_content,
            "status":     status,
            "validation": validation,
        })
        print(f"           Saved {page_id} [{status}]")

    print(f"\n[6/7] Building graph adjacency ...")
    for meta in pages_meta:
        pid     = meta["page_id"]
        content = meta["content"]
        primary = extract_yaml_list(content, "primary_links")
        for target in primary:
            if target and target != "[]":
                graph.add_link(pid, target, link_type="primary")
        for sec in extract_secondary_links(content):
            graph.add_link(pid, sec["page"], link_type="secondary", condition=sec["condition"])

    graph.save()
    print(f"      Saved adjacency to {ADJ_PATH}")

    # ── Step 7: Embed pages and build vector index ─────────────────────────
    print(f"\n[7/7] Embedding pages and building vector index ...")
    for i, meta in enumerate(pages_meta):
        page_id  = meta["page_id"]
        # strip YAML header before embedding for cleaner semantic signal
        body     = meta["content"]
        close_idx = body.find("---", 3)
        if body.startswith("---") and close_idx != -1:
            body = body[close_idx + 3:].strip()

        embedding = encode(body[:4096])  # cap at 4096 chars to avoid OOM
        vector_index.add_page(page_id, embedding)
        if (i + 1) % 10 == 0 or (i + 1) == len(pages_meta):
            print(f"      Embedded {i+1}/{len(pages_meta)} pages...")

    vector_index.save()
    print(f"      Saved vector index to {INDEX_PATH}")

    elapsed = time.time() - t_total
    print(f"\nIngestion complete. {len(pages_meta)} pages processed in {elapsed:.1f}s.")
    print(f"  Pages dir   : {PAGES_DIR}")
    print(f"  Graph file  : {ADJ_PATH}")
    print(f"  Vector index: {INDEX_PATH}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cortex Phase-1 Slack Ingestion Compiler")
    parser.add_argument("--max-messages", type=int, default=0,
                        help="Limit messages ingested (0 = no limit, use all)")
    parser.add_argument("--batch-size", type=int, default=20,
                        help="Sentence batch size for LLM classifier calls")
    args = parser.parse_args()

    # Set Groq as default if no LLM is configured
    if not os.environ.get("LLM_PROVIDER"):
        os.environ["LLM_PROVIDER"]    = "web_api"
    if not os.environ.get("AZURE_ENDPOINT") and not os.environ.get("WEB_API_ENDPOINT"):
        os.environ["AZURE_ENDPOINT"]  = "https://api.groq.com/openai/v1"
    if not os.environ.get("AZURE_API_KEY") and not os.environ.get("WEB_API_KEY"):
        os.environ["AZURE_API_KEY"]   = "<your-groq-api-key>"
    if not os.environ.get("AZURE_MODEL_NAME") and not os.environ.get("WEB_API_MODEL"):
        os.environ["AZURE_MODEL_NAME"] = "llama-3.1-8b-instant"

    run(max_messages=args.max_messages, batch_size=args.batch_size)
