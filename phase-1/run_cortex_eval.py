import os
import sys
import json
import time
import shutil

# Add parent directories to sys.path so we can import from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'app')))
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from app.ingestion.pipeline import run_ingestion_pipeline, parse_markdown_with_frontmatter
from app.storage.hnsw_index import NumPyVectorIndex
from app.storage.graph import CortexGraph
from app.llm.embedding import encode
from app.llm.kimi import get_kimi_client

def main():
    base_dir = os.path.abspath(os.path.dirname(__file__))
    csv_path = os.path.join(base_dir, 'data', 'messages.csv')
    users_path = os.path.join(base_dir, 'data', 'users.csv')
    questions_path = os.path.join(base_dir, 'eval', 'ground_truth.json')
    output_path = os.path.join(base_dir, 'eval', 'cortex_v1.json')
    
    pages_dir = os.path.join(base_dir, 'data', 'pages')
    vector_index_path = os.path.join(base_dir, 'data', 'vector_index.json')
    graph_path = os.path.join(base_dir, 'data', 'adjacency.json')
    
    print("==================================================")
    print("CORTEX END-TO-END EVALUATION RUNNER")
    print("==================================================")
    
    # Step 1: Ensure Ollama and LLM Provider are working
    print("\n--- [Step 1] Initializing LLM Client & Starting Ollama ---")
    try:
        client = get_kimi_client()
        print("LLM Client initialized successfully.")
    except Exception as e:
        print(f"Error initializing LLM Client: {e}")
        sys.exit(1)
        
    # Step 2: Run Ingestion Pipeline
    print("\n--- [Step 2] Ingesting Slack data (limit 200 messages) ---")
    if os.path.exists(pages_dir):
        print(f"Cleaning existing pages directory: {pages_dir}")
        shutil.rmtree(pages_dir)
    os.makedirs(pages_dir, exist_ok=True)
    
    # We run ingestion with max_messages=200 as a small scale test
    try:
        pages = run_ingestion_pipeline(csv_path, max_messages=200, max_clusters=None)
        print(f"Ingestion pipeline completed. Generated {len(pages)} pages.")
    except Exception as e:
        print(f"Error running ingestion pipeline: {e}")
        sys.exit(1)
        
    # Step 3: Write Pages and Build Indices
    print("\n--- [Step 3] Serializing pages and building vector/graph indices ---")
    vector_index = NumPyVectorIndex(vector_index_path, dim=384)
    graph = CortexGraph(graph_path)
    
    # Clear any old data
    vector_index.page_ids = []
    vector_index.embeddings = []
    graph.graph = {}
    
    for idx, page in enumerate(pages):
        page_id = page["page_id"]
        content = page["content"]
        
        # Save page file
        page_file = os.path.join(pages_dir, f"{page_id}.md")
        with open(page_file, "w", encoding="utf-8") as f:
            f.write(content)
            
        # Parse frontmatter to add to graph
        metadata, body = parse_markdown_with_frontmatter(content)
        
        # We index the text content of the page (title + body)
        title = metadata.get("title", f"Page {page_id}")
        indexing_text = f"Title: {title}\n\n{body}"
        
        # Generate embedding
        print(f"  [{idx+1}/{len(pages)}] Embedding page {page_id}...")
        emb = encode(indexing_text)
        vector_index.add_page(page_id, emb)
        
        # Add to graph
        if page_id not in graph.graph:
            graph.graph[page_id] = {"primary": [], "secondary": []}
            
        primary = metadata.get("primary_links", []) or []
        for to_page in primary:
            graph.add_link(page_id, to_page, "primary")
            
        secondary = metadata.get("secondary_links", []) or []
        for item in secondary:
            if isinstance(item, dict):
                cond = item.get("condition")
                to_page = item.get("page")
                if cond and to_page:
                    graph.add_link(page_id, to_page, "secondary", cond)
                    
    # Save indices
    vector_index.save()
    graph.save()
    print("Vector index and graph store saved successfully.")
    
    # Step 4: Run Evaluation on Questions
    print("\n--- [Step 4] Querying 50 ground truth questions ---")
    if not os.path.exists(questions_path):
        print(f"Error: ground_truth.json not found at {questions_path}")
        sys.exit(1)
        
    with open(questions_path, 'r', encoding='utf-8') as f:
        qa_pairs = json.load(f)
        
    results = []
    total_questions = len(qa_pairs)
    print(f"Starting evaluation on {total_questions} questions...")
    
    for idx, pair in enumerate(qa_pairs):
        question = pair['question']
        print(f"\n[{idx+1}/{total_questions}] Question: {question}")
        
        try:
            start_time = time.time()
            
            # 1. Embed query
            query_vector = encode(question)
            
            # 2. Search entry pages (top-3)
            candidates_with_scores = vector_index.search(query_vector, k=3)
            entry_pages = [page_id for page_id, score in candidates_with_scores]
            print(f"  Entry pages found: {entry_pages}")
            
            # 3. Traverse graph
            pages_to_read, path, gaps = graph.traverse(
                entry_pages, 
                question, 
                vector_index=vector_index, 
                query_vector=query_vector, 
                similarity_threshold=0.65
            )
            print(f"  Pages to read (after traversal & safety net): {pages_to_read}")
            
            # 4. Construct context
            context_blocks = []
            for page_id in pages_to_read:
                page_file = os.path.join(pages_dir, f"{page_id}.md")
                if os.path.exists(page_file):
                    with open(page_file, "r", encoding="utf-8") as f:
                        pg_content = f.read()
                    context_blocks.append(f"--- Document [ID: {page_id}] ---\n{pg_content}")
            
            if not context_blocks:
                cortex_answer = "No relevant knowledge pages found to answer this question."
            else:
                context_str = "\n\n".join(context_blocks)
                
                # 5. Generate Answer using LLM
                prompt = (
                    "You are Cortex, a highly precise corporate Knowledge assistant.\n"
                    "Below are relevant canonical knowledge pages synthesized from the company's workspace.\n"
                    "Use this context to answer the question as accurately and completely as possible.\n"
                    "If the information is not in the context, state that honestly.\n"
                    "Always cite your sources by referencing the page ID or specific sources in the page when asserting facts.\n\n"
                    "=== CONTEXT ===\n"
                    f"{context_str}\n\n"
                    f"Question: {question}\n\n"
                    "Answer:"
                )
                
                cortex_answer = client.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=2048
                )
                
            latency = (time.time() - start_time) * 1000
            print(f"  Latency: {latency:.1f}ms")
            
            results.append({
                "question": question,
                "gold_answer": pair['answer'],
                "cortex_answer": cortex_answer,
                "pages_read": pages_to_read,
                "had_knowledge_gap": len(gaps) > 0,
                "latency_ms": int(latency)
            })
            
        except Exception as e:
            print(f"  Error querying Cortex: {e}")
            results.append({
                "question": question,
                "gold_answer": pair['answer'],
                "cortex_answer": f"ERROR: {e}",
                "pages_read": [],
                "had_knowledge_gap": True,
                "latency_ms": 0
            })
            
    # Save benchmark result
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
        
    print("\n==================================================")
    print(f"Cortex evaluation completed! Saved to {output_path}")
    print("==================================================")

if __name__ == '__main__':
    main()
