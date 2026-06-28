import os
import re
import sys
import json
import datetime
import yaml

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from app.database.connection import get_tenant_connection
from app.ingestion.synthesizer import synthesize_page
from app.ingestion.validation import validate_page
from app.llm.embedding import encode
from app.storage.git_store import init_tenant_repo, commit_page_changes, get_tenant_repo_dir
from app.storage.hnsw_index import NumPyVectorIndex
from app.storage.graph import CortexGraph
from app.ingestion.pipeline import extract_yaml_list, extract_secondary_links

def relink_and_restyle(tenant_id: str = "tenant_a"):
    print(f"Starting Relinking & Restyling migration for tenant: {tenant_id}...")
    
    # Initialize Git repository and paths for this tenant
    repo = init_tenant_repo(tenant_id)
    repo_dir = get_tenant_repo_dir(tenant_id)
    
    tenant_dir = os.path.dirname(repo_dir)
    index_path = os.path.join(tenant_dir, "vector_index.json")
    adj_path = os.path.join(tenant_dir, "graph", "adjacency.json")
    
    if not os.path.exists(repo_dir):
        print(f"Repository directory does not exist: {repo_dir}")
        return
        
    # 1. Build the catalog of existing pages
    existing_pages_catalog = []
    page_files = [f for f in os.listdir(repo_dir) if f.startswith("page_") and f.endswith(".md")]
    page_files.sort()
    
    print(f"Found {len(page_files)} pages in the repository.")
    
    for f in page_files:
        pid = f[:-3]
        f_path = os.path.join(repo_dir, f)
        with open(f_path, "r", encoding="utf-8") as pf:
            p_content = pf.read()
            m_title = re.search(r"^title:\s*(.+)$", p_content, re.MULTILINE)
            p_title = m_title.group(1).strip() if m_title else f"Page {pid}"
            existing_pages_catalog.append(f"{pid}: {p_title}")
            
    print(f"Created catalog of existing pages:\n" + "\n".join([f"  - {item}" for item in existing_pages_catalog]))
    
    pages_meta = []
    
    # 2. Iterate through pages and re-synthesize them
    for f in page_files:
        pid = f[:-3]
        f_path = os.path.join(repo_dir, f)
        print(f"\nProcessing {pid}...")
        
        with open(f_path, "r", encoding="utf-8") as pf:
            content = pf.read()
            
        # Parse YAML frontmatter
        parts = content.split("---")
        if len(parts) < 3:
            print(f"Warning: {f} does not have valid YAML frontmatter delimiters.")
            continue
            
        try:
            metadata = yaml.safe_load(parts[1])
        except Exception as e:
            print(f"Error parsing YAML in {f}: {e}")
            continue
            
        props = metadata.get("propositions", [])
        if not props:
            print(f"No propositions found in {f}. Skipping.")
            continue
            
        # Reconstruct message cluster format
        cluster = []
        for prop in props:
            cluster.append({
                "text": prop.get("text", ""),
                "type": "PRESCRIPTION",
                "metadata": {
                    "user": "system",
                    "channel": "relink",
                    "timestamp": metadata.get("last_updated", ""),
                    "source_id": metadata.get("sources", ["slack://system"])[0]
                }
            })
            
        m_idx = re.search(r"page_(\d+)", pid)
        page_index = int(m_idx.group(1)) if m_idx else 1
        
        print(f"Re-synthesizing {pid} content with AI model...")
        new_content = synthesize_page(
            page_index=page_index,
            cluster=cluster,
            feedback=None,
            temperature=0.3,
            tenant_id=tenant_id,
            existing_pages_catalog=existing_pages_catalog
        )
        
        # Validate synthesis
        sources = [item["text"] for item in cluster]
        validation = validate_page(sources, new_content, tenant_id=tenant_id)
        passed = validation.get("validation_passed", False)
        
        # Inject validation scores block into YAML header
        val_block = (
            f"synthesis_validation:\n"
            f"  proposition_coverage: {validation.get('proposition_coverage', 0.0):.2f}\n"
            f"  hallucination_rate: {validation.get('hallucination_rate', 1.0):.2f}\n"
            f"  completeness_score: {validation.get('completeness_score', 1)}\n"
            f"  validation_passed: {str(passed).lower()}\n"
            f"  validated_at: {datetime.datetime.utcnow().isoformat()}Z\n"
        )
        if new_content.startswith("---"):
            close = new_content.find("---", 3)
            if close != -1:
                new_content = new_content[:close] + val_block + new_content[close:]
                
        # Write back to file
        with open(f_path, "w", encoding="utf-8") as pf:
            pf.write(new_content)
            
        # Commit file changes in Git
        commit_msg = f"relink: Update {pid} with new formatting and cross-links"
        commit_page_changes(tenant_id, pid, commit_msg)
        
        pages_meta.append({
            "page_id": pid,
            "content": new_content,
            "validation": validation,
            "sources": sources
        })
        print(f"Finished {pid} updates.")
        
    # 3. Rebuild Graph Adjacency List
    print("\nRebuilding graph adjacency map...")
    graph = CortexGraph(adjacency_path=adj_path)
    graph.adjacency = {} # reset active links to start fresh
    
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
    print("Graph adjacency map rebuilt successfully.")
    
    # 4. Rebuild HNSW Vector index
    print("\nReindexing vector databases...")
    vector_index = NumPyVectorIndex(index_path=index_path, dim=384)
    # Clear vector index keys for fresh start
    vector_index.keys = []
    vector_index.embeddings = None
    
    for meta in pages_meta:
        page_id = meta["page_id"]
        body = meta["content"]
        close_idx = body.find("---", 3)
        if body.startswith("---") and close_idx != -1:
            body = body[close_idx + 3:].strip()
            
        embedding = encode(body[:4096])
        vector_index.add_page(page_id, embedding)
        
    vector_index.save()
    print("Vector indices re-indexed successfully.")
    print("\nRelinking & Restyling migration completed successfully!")

if __name__ == "__main__":
    relink_and_restyle("tenant_a")
