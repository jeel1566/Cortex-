import os
import csv
import json
import re
import sys
import math
import time
import numpy as np
from collections import Counter
from typing import List, Dict, Tuple, Any
from datetime import datetime

# Add parent directories to sys.path so we can import from app
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from llama_index.core import VectorStoreIndex, Document, Settings
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.query_engine import BaseQueryEngine
from llama_index.core.base.response.schema import Response
from app.llm.kimi import KimiLlamaIndexLLM

def load_user_mappings(users_csv):
    user_map = {}
    if not users_csv or not os.path.exists(users_csv):
        return user_map
    try:
        with open(users_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                uid = row.get('id', '')
                name = row.get('name', '')
                real_name = row.get('real_name', '')
                if uid:
                    user_map[uid] = real_name or name or uid
    except Exception as e:
        print(f"Warning loading users: {e}")
    return user_map

def redact_pii(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '[EMAIL]', text)
    text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', text)
    text = re.sub(r'\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}', '[PHONE]', text)
    return text

def replace_user_mentions(text: str, user_map: dict) -> str:
    if not text:
        return ""
    def replace_match(match):
        uid = match.group(1)
        return f"@{user_map.get(uid, uid)}"
    # Replace <@U12345> style mentions
    return re.sub(r'<@(U[A-Z0-9]+)>', replace_match, text)

def parse_ts_to_float(ts_str: str) -> float:
    if not ts_str:
        return 0.0
    try:
        return float(ts_str)
    except ValueError:
        try:
            dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
            return dt.timestamp()
        except:
            return 0.0

def load_slack_documents(messages_csv, users_csv):
    user_map = load_user_mappings(users_csv)
    
    # 1. Load messages
    raw_messages = []
    if not os.path.exists(messages_csv):
        print(f"CSV file not found: {messages_csv}")
        return []
        
    with open(messages_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = row.get('ts', '')
            thread_ts = row.get('thread_ts', '') or ts
            subtype = row.get('subtype', '')
            text = row.get('text', '') or ''
            user_id = row.get('user', '') or 'unknown_user'
            channel_id = row.get('channel_id', '') or 'unknown_channel'
            
            # Filter junk subtypes (joins/leaves)
            if subtype in ['channel_join', 'channel_leave']:
                continue
                
            raw_messages.append({
                "ts": ts,
                "thread_ts": thread_ts,
                "user_id": user_id,
                "user_name": user_map.get(user_id, user_id),
                "text": text,
                "channel_id": channel_id
            })
            
    # 2. Group messages by thread_ts and channel_id to preserve conversation threads
    threads = {}
    for msg in raw_messages:
        key = (msg["channel_id"], msg["thread_ts"])
        if key not in threads:
            threads[key] = []
        threads[key].append(msg)
        
    documents = []
    for (channel_id, thread_ts), msgs in threads.items():
        # Sort messages in the thread by timestamp
        msgs.sort(key=lambda x: parse_ts_to_float(x["ts"]))
        
        # Build threaded conversation view
        thread_lines = []
        full_text_list = []
        
        for msg in msgs:
            clean_text = replace_user_mentions(msg["text"], user_map)
            clean_text = redact_pii(clean_text)
            
            # Skip empty or short messages after cleaning, unless they are part of a thread
            if len(clean_text.strip()) < 10 and len(msgs) == 1:
                continue
                
            # Convert timestamp to human readable
            try:
                dt = datetime.fromtimestamp(float(msg["ts"])).strftime('%Y-%m-%d %H:%M:%S')
            except:
                dt = msg["ts"]
                
            line = f"{msg['user_name']} [{dt}]: {clean_text}"
            thread_lines.append(line)
            full_text_list.append(clean_text)
            
        if not thread_lines:
            continue
            
        # Join messages with newlines
        doc_content = f"Channel: {channel_id}\n" + "\n".join(thread_lines)
        
        # Filter out overall short threads/messages to avoid noise
        full_text = " ".join(full_text_list)
        if len(full_text.split()) < 10:
            continue
            
        doc = Document(
            text=doc_content,
            metadata={
                "channel_id": channel_id,
                "thread_ts": thread_ts,
                "message_count": len(msgs)
            }
        )
        documents.append(doc)
        
    return documents

class BM25:
    def __init__(self, documents: List[List[str]], k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.documents = documents
        self.doc_len = [len(doc) for doc in documents]
        self.avgdl = sum(self.doc_len) / len(documents) if documents else 0
        self.doc_freqs = []
        self.nd = {}  # Word -> number of docs containing word
        self.N = len(documents)
        
        for doc in documents:
            frequencies = Counter(doc)
            self.doc_freqs.append(frequencies)
            for word in frequencies:
                self.nd[word] = self.nd.get(word, 0) + 1
                
        self.idf = {}
        for word, freq in self.nd.items():
            self.idf[word] = math.log((self.N - freq + 0.5) / (freq + 0.5) + 1.0)
            
    def get_score(self, query: List[str], index: int) -> float:
        score = 0.0
        doc_freq = self.doc_freqs[index]
        d_len = self.doc_len[index]
        
        for word in query:
            if word not in doc_freq:
                continue
            idf_val = self.idf.get(word, 0)
            tf = doc_freq[word]
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * (d_len / self.avgdl))
            score += idf_val * (numerator / denominator)
            
        return score

    def search(self, query: List[str], top_k=10) -> List[Tuple[int, float]]:
        scores = [(i, self.get_score(query, i)) for i in range(self.N)]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class BestSlackRAGQueryEngine(BaseQueryEngine):
    def __init__(self, documents, embed_model, llm, similarity_top_k=10, rerank_top_k=3):
        super().__init__(callback_manager=Settings.callback_manager)
        self.documents = documents
        self.embed_model = embed_model
        self.llm = llm
        self.similarity_top_k = similarity_top_k
        self.rerank_top_k = rerank_top_k
        
        # Build BM25 index
        doc_texts = [doc.text for doc in documents]
        tokenized_docs = [re.findall(r'\w+', text.lower()) for text in doc_texts]
        self.bm25 = BM25(tokenized_docs)
        
        # Build Semantic index
        print("Computing embeddings for documents in batch...")
        doc_texts = [doc.text for doc in documents]
        self.doc_embeddings = embed_model.get_text_embedding_batch(doc_texts)

    def _get_prompt_modules(self) -> Dict[str, Any]:
        return {}

    def _get_prompts(self) -> Dict[str, Any]:
        return {}

    def _update_prompts(self, prompts: Dict[str, Any]) -> None:
        pass
            
    def _query(self, query_bundle) -> Response:
        if isinstance(query_bundle, str):
            query_str = query_bundle
        else:
            query_str = query_bundle.query_str
            
        import time
        start_time = time.time()
        
        # 1. Query Expansion
        t0 = time.time()
        expanded_queries = self._expand_query(query_str)
        t_expansion = (time.time() - t0) * 1000
        
        # 2. Hybrid Retrieval
        t0 = time.time()
        candidate_indices = self._hybrid_retrieve(expanded_queries, query_str)
        t_retrieval = (time.time() - t0) * 1000
        
        # 3. LLM Reranking
        t0 = time.time()
        top_indices = self._rerank(query_str, candidate_indices)
        t_reranking = (time.time() - t0) * 1000
        
        # 4. Generation
        t0 = time.time()
        final_answer = self._generate_answer(query_str, top_indices)
        t_generation = (time.time() - t0) * 1000
        
        total_time = (time.time() - start_time) * 1000
        
        # Logging Telemetry
        print(f"\n--- RAG Latency Report ---")
        print(f"Query: '{query_str}'")
        print(f"  Query Expansion: {t_expansion:.1f}ms")
        print(f"  Hybrid Retrieval: {t_retrieval:.1f}ms (candidates: {len(candidate_indices)})")
        print(f"  LLM Reranking: {t_reranking:.1f}ms (selected: {len(top_indices)})")
        print(f"  Generation: {t_generation:.1f}ms")
        print(f"  Total Latency: {total_time:.1f}ms")
        print(f"--------------------------\n")
        
        return Response(response=final_answer)

    async def _aquery(self, query_bundle) -> Response:
        return self._query(query_bundle)

    def _expand_query(self, query_str: str) -> List[str]:
        prompt = (
            "You are an expert search system for a company's Slack logs. "
            "Your task is to take a user's search query and generate 3 alternative search queries "
            "or keyword lists that will help retrieve the relevant Slack message threads. "
            "Expand abbreviations (e.g. 'SIP' to 'Superset Improvement Proposal'), resolve "
            "potential names, and add synonyms.\n\n"
            f"Original query: {query_str}\n\n"
            "Respond ONLY with a JSON list of strings. Example: [\"original query\", \"expanded query 1\", \"expanded query 2\"]"
        )
        try:
            from app.llm.kimi import get_kimi_client
            client = get_kimi_client()
            response = client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            
            data = json.loads(clean_response)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "queries" in data:
                return data["queries"]
            elif isinstance(data, dict):
                for v in data.values():
                    if isinstance(v, list):
                        return v
        except Exception as e:
            print(f"Warning during query expansion: {e}")
        return [query_str]

    def _hybrid_retrieve(self, expanded_queries: List[str], original_query: str) -> List[int]:
        query_vector = self.embed_model.get_query_embedding(original_query)
        
        # 1. Semantic Search
        q_vec = np.array(query_vector)
        matrix = np.array(self.doc_embeddings)
        
        q_norm = np.linalg.norm(q_vec)
        matrix_norms = np.linalg.norm(matrix, axis=1)
        q_norm = q_norm if q_norm != 0 else 1.0
        matrix_norms[matrix_norms == 0] = 1.0
        
        dot_products = np.dot(matrix, q_vec)
        similarities = dot_products / (matrix_norms * q_norm)
        
        semantic_ranking = np.argsort(similarities)[::-1]
        
        # 2. BM25 Search
        all_query_terms = []
        for q in expanded_queries:
            all_query_terms.extend(re.findall(r'\w+', q.lower()))
        all_query_terms = list(set(all_query_terms))
        
        bm25_ranking = [idx for idx, score in self.bm25.search(all_query_terms, top_k=len(self.documents))]
        
        # 3. Reciprocal Rank Fusion (RRF)
        rrf_scores = {}
        k = 60
        
        for rank, idx in enumerate(semantic_ranking):
            rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (k + rank)
            
        for rank, idx in enumerate(bm25_ranking):
            rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (k + rank)
            
        sorted_candidates = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return [idx for idx, score in sorted_candidates[:self.similarity_top_k]]

    def _rerank(self, query_str: str, candidate_indices: List[int]) -> List[int]:
        if not candidate_indices:
            return []
            
        candidates_formatted = []
        for rank, idx in enumerate(candidate_indices):
            doc = self.documents[idx]
            snippet = doc.text[:400].replace('\n', ' ')
            candidates_formatted.append(f"Candidate ID: {idx}\nSnippet: {snippet}...")
            
        prompt = (
            "You are an expert reranking system for a search engine. "
            f"We have retrieved the following candidate Slack threads for the query: '{query_str}'\n\n"
            + "\n\n".join(candidates_formatted) + "\n\n"
            "Your task is to analyze the user's query and select the top 3 Candidate IDs that are most likely to answer the query, "
            "ordered from most relevant to least relevant.\n"
            "Respond ONLY with a JSON list of integers representing the chosen Candidate IDs. "
            "Example: [4, 12, 1]"
        )
        
        try:
            from app.llm.kimi import get_kimi_client
            client = get_kimi_client()
            response = client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1
            )
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            
            data = json.loads(clean_response)
            if isinstance(data, list):
                valid_indices = [int(x) for x in data if int(x) in candidate_indices]
                if valid_indices:
                    return valid_indices[:self.rerank_top_k]
        except Exception as e:
            print(f"Warning during LLM reranking: {e}")
            
        return candidate_indices[:self.rerank_top_k]

    def _generate_answer(self, query_str: str, top_indices: List[int]) -> str:
        if not top_indices:
            return "No relevant Slack messages found to answer this question."
            
        context_blocks = []
        for idx in top_indices:
            doc = self.documents[idx]
            context_blocks.append(f"--- Document [ID: {idx}] ---\n{doc.text}")
            
        prompt = (
            "You are Cortex, a highly precise corporate Knowledge assistant. "
            "Below are relevant Slack message threads from the company's workspace. "
            "Use this context to answer the question as accurately and completely as possible. "
            "If the information is not in the context, state that honestly. "
            "Always cite your sources by referencing the name, timestamp, or channel when asserting facts.\n\n"
            "=== CONTEXT ===\n"
            + "\n\n".join(context_blocks) + "\n\n"
            f"Question: {query_str}\n\n"
            "Answer:"
        )
        
        try:
            from app.llm.kimi import get_kimi_client
            client = get_kimi_client()
            response = client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=2048
            )
            return response
        except Exception as e:
            return f"Error generating answer: {e}"


def get_query_engine(csv_path, users_path):
    # 1. Config local embeddings (CPU friendly)
    embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
    Settings.embed_model = embed_model
    
    # 2. Config custom Kimi LLM
    llm = KimiLlamaIndexLLM()
    Settings.llm = llm
    
    # 3. Load documents and build in-memory index
    print("Loading and preprocessing Slack documents (threads, users mapping, PII redaction)...")
    documents = load_slack_documents(csv_path, users_path)
    print(f"Ingested {len(documents)} threaded documents.")
    
    print("Creating advanced BestSlackRAGQueryEngine...")
    query_engine = BestSlackRAGQueryEngine(documents, embed_model, llm)
    return query_engine

def run_evaluation(csv_path, users_path, questions_path, output_path):
    try:
        query_engine = get_query_engine(csv_path, users_path)
    except Exception as e:
        print(f"Error initializing RAG engine: {e}")
        return
        
    with open(questions_path, 'r', encoding='utf-8') as f:
        qa_pairs = json.load(f)
        
    results = []
    print(f"Starting evaluation on {len(qa_pairs)} questions...")
    for idx, pair in enumerate(qa_pairs):
        question = pair['question']
        print(f"[{idx+1}/{len(qa_pairs)}] Question: {question}")
        try:
            response = query_engine.query(question)
            results.append({
                "question": question,
                "gold_answer": pair['answer'],
                "rag_answer": str(response)
            })
        except Exception as e:
            print(f"Error querying RAG: {e}")
            results.append({
                "question": question,
                "gold_answer": pair['answer'],
                "rag_answer": f"ERROR: {e}"
            })
            
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"RAG baseline evaluation results saved to {output_path}")

if __name__ == '__main__':
    # Default paths relative to this script's directory for maximum portability
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    csv_path = os.path.join(base_dir, 'data', 'messages.csv')
    users_path = os.path.join(base_dir, 'data', 'users.csv')
    questions_path = os.path.join(base_dir, 'eval', 'ground_truth.json')
    output_path = os.path.join(base_dir, 'eval', 'rag_baseline.json')
    
    run_evaluation(csv_path, users_path, questions_path, output_path)
