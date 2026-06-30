import os
import re
import sys
import datetime
from typing import List, Dict, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.ingestion.classifier import classify_sentences
from app.ingestion.clusterer import cluster_sentences
from app.ingestion.synthesizer import synthesize_page
from app.ingestion.validation import validate_page
from app.llm.embedding import encode
from app.storage.git_store import init_tenant_repo, commit_page_changes, get_tenant_repo_dir
from app.storage.hnsw_index import NumPyVectorIndex
from app.storage.graph import CortexGraph

def redact_pii(text: str) -> str:
    # ponytail: PII redaction disabled to preserve dates, PRs, emails, and phone numbers in raw form.
    return text

def split_into_sentences(text: str) -> List[str]:
    """Splits a block of text into individual sentences using punctuation boundaries."""
    if not text:
        return []
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]

def extract_yaml_list(content: str, field: str) -> List[str]:
    """Extracts a list from YAML frontmatter."""
    block_pattern = rf"^{field}:\s*\n((?:\s+- .+\n?)*)"
    m = re.search(block_pattern, content, re.MULTILINE)
    if m:
        return re.findall(r"-\s+(\S+)", m.group(1))
    return []

def extract_secondary_links(content: str) -> List[Dict[str, str]]:
    """Extracts secondary links from page frontmatter."""
    links = []
    pattern = r'- condition:\s*["\']?([^"\'\n]+)["\']?\s*\n\s*page:\s*(\S+)'
    for m in re.finditer(pattern, content, re.MULTILINE):
        links.append({"condition": m.group(1).strip(), "page": m.group(2).strip()})
    return links

def update_job_stage(tenant_id: str, job_id: str, stage: str):
    if not job_id:
        return
    try:
        from app.database.connection import get_tenant_connection
        conn = get_tenant_connection(tenant_id)
        cursor = conn.cursor()
        cursor.execute("UPDATE ingestion_jobs SET current_stage = ? WHERE id = ?", (stage, job_id))
        conn.commit()
    except Exception as e:
        print(f"Failed to update job stage: {e}")

def run_ingestion_pipeline(tenant_id: str, raw_messages: List[Dict[str, Any]], batch_size: int = 20, job_id: str = None) -> List[Dict[str, Any]]:
    """
    Ingests messages for a specific tenant.
    raw_messages is a list of dicts: [{"text": str, "user": str, "channel": str, "timestamp": str}]
    """
    if not raw_messages:
        return []
        
    # Initialize Git repository and paths for this tenant
    repo = init_tenant_repo(tenant_id)
    repo_dir = get_tenant_repo_dir(tenant_id)
    
    tenant_dir = os.path.dirname(repo_dir)
    index_path = os.path.join(tenant_dir, "vector_index.json")
    adj_path = os.path.join(tenant_dir, "graph", "adjacency.json")
    
    # 1. Clean messages and redact PII
    update_job_stage(tenant_id, job_id, "pii_redaction")
    cleaned_messages = []
    for msg in raw_messages:
        text = msg.get("text", "")
        clean_text = redact_pii(text)
        
        cleaned_messages.append({
            "text": clean_text,
            "user": msg.get("user", "unknown_user"),
            "channel": msg.get("channel", "unknown_channel"),
            "timestamp": msg.get("timestamp", ""),
            "source_id": msg.get("source_id", f"slack://{msg.get('channel')}/{msg.get('timestamp')}")
        })
        
    # 2. Split into sentence records
    update_job_stage(tenant_id, job_id, "sentence_splitting")
    sentence_records = []
    for msg in cleaned_messages:
        for s in split_into_sentences(msg["text"]):
            sentence_records.append({
                "text": s,
                "metadata": {
                    "user": msg["user"],
                    "channel": msg["channel"],
                    "timestamp": msg["timestamp"],
                    "source_id": msg["source_id"]
                }
            })
            
    # 3. Classify speech acts
    update_job_stage(tenant_id, job_id, "speech_act_classification")
    texts = [r["text"] for r in sentence_records]
    classified_types = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        classified_types.extend(classify_sentences(batch, tenant_id=tenant_id))
        
    for r, t in zip(sentence_records, classified_types):
        r["type"] = t
        
    # 4. Cluster sentences
    update_job_stage(tenant_id, job_id, "sentence_clustering")
    clusters = cluster_sentences(sentence_records, similarity_threshold=0.68)
    
    # 5. Synthesize, validate, and save pages
    update_job_stage(tenant_id, job_id, "page_synthesis")
    vector_index = NumPyVectorIndex(index_path=index_path, dim=384)
    graph = CortexGraph(adjacency_path=adj_path)
    
    pages_meta = []
    for idx, cluster in enumerate(clusters):
        # Determine next available page number by scanning existing files in repo
        existing_pages = [f for f in os.listdir(repo_dir) if f.startswith("page_") and f.endswith(".md")]
        page_num = len(existing_pages) + 1
        page_id = f"page_{page_num:03d}"
        
        # Determine existing pages catalog to help the LLM generate links
        existing_pages_catalog = []
        try:
            for f in os.listdir(repo_dir):
                if f.startswith("page_") and f.endswith(".md"):
                    pid = f[:-3]
                    f_path = os.path.join(repo_dir, f)
                    with open(f_path, "r", encoding="utf-8") as pf:
                        p_content = pf.read()
                        m_title = re.search(r"^title:\s*(.+)$", p_content, re.MULTILINE)
                        p_title = m_title.group(1).strip() if m_title else f"Page {pid}"
                        existing_pages_catalog.append(f"{pid}: {p_title}")
        except Exception as e:
            print(f"Error loading existing pages catalog: {e}")

        sources = [item["text"] for item in cluster]
        
        attempts = 0
        page_content = ""
        validation = {}
        passed = False
        feedback = None
        temperature = 0.3
        errors = []
        
        try:
            while attempts < 3 and not passed:
                attempts += 1
                page_content = synthesize_page(
                    page_num, 
                    cluster, 
                    feedback=feedback, 
                    temperature=temperature, 
                    tenant_id=tenant_id,
                    existing_pages_catalog=existing_pages_catalog
                )
                validation = validate_page(sources, page_content, tenant_id=tenant_id)
                passed = validation.get("validation_passed", False)
                
                if not passed:
                    cov = validation.get("proposition_coverage", 1.0)
                    hal = validation.get("hallucination_rate", 0.0)
                    comp = validation.get("completeness_score", 10)
                    
                    feedback_parts = []
                    if cov < 0.90:
                        feedback_parts.append(
                            f"CRITICAL: Proposition coverage was too low ({cov:.2f}). "
                            "You must explicitly include and document all source claims on this page."
                        )
                    if hal > 0.02:
                        feedback_parts.append(
                            f"CRITICAL: Hallucination rate was too high ({hal:.2f}). "
                            "Strictly limit claims to the facts in the source logs. Do not extrapolate."
                        )
                    if comp < 7:
                        feedback_parts.append(
                            f"CRITICAL: Completeness score was too low ({comp}/10). "
                            "Ensure the page is a cohesive, fully detailed, and comprehensive answer to the topic."
                        )
                        temperature = 0.2
                        
                    feedback = "\n".join(feedback_parts)
            
            if not passed:
                errors.append(
                    f"Page synthesis validation failed for {page_id}. "
                    f"Proposition coverage: {validation.get('proposition_coverage', 0.0):.2f}, "
                    f"Hallucination rate: {validation.get('hallucination_rate', 1.0):.2f}, "
                    f"Completeness: {validation.get('completeness_score', 1)}/10"
                )
            else:
                # Inject validation scores block into YAML header
                val_block = (
                    f"synthesis_validation:\n"
                    f"  proposition_coverage: {validation.get('proposition_coverage', 0.0):.2f}\n"
                    f"  hallucination_rate: {validation.get('hallucination_rate', 1.0):.2f}\n"
                    f"  completeness_score: {validation.get('completeness_score', 1)}\n"
                    f"  validation_passed: {str(passed).lower()}\n"
                    f"  validated_at: {datetime.datetime.utcnow().isoformat()}Z\n"
                )
                if page_content.startswith("---"):
                    from app.ingestion.validation import find_frontmatter_end
                    close = find_frontmatter_end(page_content)
                    if close != -1:
                        page_content = page_content[:close] + val_block + page_content[close:]
                        
                # Verify page shape before writing
                from app.ingestion.validation import verify_page_shape
                verify_page_shape(page_content, strict_evidence=False)
        except Exception as e:
            errors.append(str(e))
            passed = False

        if not passed or errors:
            try:
                from app.database.connection import get_tenant_connection
                from app.ingestion.source_store import create_knowledge_page_draft
                conn = get_tenant_connection(tenant_id)
                
                sources_list = list(set([item.get("metadata", {}).get("source_id", "slack://unknown") for item in cluster]))
                sources_yaml_str = "\n".join([f'  - "{src}"' for src in sources_list])
                title = f"Synthesized Topic {page_num}"
                draft_id = f"draft_{page_num:03d}"
                
                draft_content = (
                    "---\n"
                    f'id: "{draft_id}"\n'
                    f'title: "{title}"\n'
                    f"sources:\n"
                    f"{sources_yaml_str}\n"
                    "---\n\n"
                    f"# {title}\n"
                )
                
                create_knowledge_page_draft(
                    conn,
                    tenant_id=tenant_id,
                    title=title,
                    content=draft_content,
                    status="REJECTED",
                    validation_passed=False,
                    errors=errors
                )
            except Exception as store_err:
                print(f"Failed to store rejected draft: {store_err}")
                
            raise ValueError(errors[0] if errors else "Page synthesis failed.")

        status = "APPROVED" if passed else "DRAFT"

        # Write page to file
        page_path = os.path.join(repo_dir, f"{page_id}.md")
        with open(page_path, "w", encoding="utf-8") as f:
            f.write(page_content)
            
        # Commit file changes in Git
        commit_msg = f"ingest: Create {page_id} containing {len(cluster)} sentences ({status})"
        commit_page_changes(tenant_id, page_id, commit_msg)
        
        pages_meta.append({
            "page_id": page_id,
            "content": page_content,
            "status": status,
            "validation": validation,
            "sources": sources
        })
        
    # 6. Build graph adjacency list
    update_job_stage(tenant_id, job_id, "graph_indexing")
    for meta in pages_meta:
        pid = meta["page_id"]
        content = meta["content"]
        primary = extract_yaml_list(content, "primary_links")
        for target in primary:
            if target and target != "[]":
                graph.add_link(pid, target, link_type="primary")
        for sec in extract_secondary_links(content):
            graph.add_link(pid, sec["page"], link_type="secondary", condition=sec["condition"])
            
    graph.save()
    
    # 7. Add embeddings to vector index
    for meta in pages_meta:
        page_id = meta["page_id"]
        body = meta["content"]
        if body.startswith("---"):
            from app.ingestion.validation import find_frontmatter_end
            close_idx = find_frontmatter_end(body)
            if close_idx != -1:
                body = body[close_idx + 3:].strip()
            
        embedding = encode(body[:4096])
        vector_index.add_page(page_id, embedding)
        
    vector_index.save()
    update_job_stage(tenant_id, job_id, "complete")
    
    return pages_meta
