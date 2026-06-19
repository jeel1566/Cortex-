import os
import re
import csv
import sys
import datetime
import yaml
import json
from typing import List, Dict, Any, Tuple

# Add parent directories to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.ingestion.classifier import classify_sentences
from app.ingestion.clusterer import cluster_sentences
from app.ingestion.synthesizer import synthesize_page
from app.ingestion.validation import validate_page

def parse_markdown_with_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Parses a markdown string containing a YAML frontmatter block."""
    if not content.startswith("---"):
        return {}, content
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content
    try:
        metadata = yaml.safe_load(parts[1])
        if not isinstance(metadata, dict):
            metadata = {}
        return metadata, parts[2].strip()
    except Exception as e:
        print(f"Error parsing YAML frontmatter: {e}")
        return {}, content

def serialize_markdown_with_frontmatter(metadata: Dict[str, Any], body: str) -> str:
    """Serializes metadata and body back into a Markdown document with YAML frontmatter."""
    yaml_str = yaml.safe_dump(metadata, default_flow_style=False, sort_keys=False)
    return f"---\n{yaml_str.strip()}\n---\n\n{body}"

def load_user_mappings(users_csv: str) -> Dict[str, str]:
    """Loads user mapping from CSV, formatting as Name [UserID] to preserve original ID."""
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
                    mapped_name = real_name or name or uid
                    if mapped_name != uid:
                        user_map[uid] = f"{mapped_name} [{uid}]"
                    else:
                        user_map[uid] = uid
    except Exception as e:
        print(f"Warning loading users: {e}")
    return user_map

def replace_user_mentions(text: str, user_map: dict) -> str:
    """Replaces Slack <@U12345> mentions with name + original ID."""
    if not text:
        return ""
    def replace_match(match):
        uid = match.group(1)
        return f"@{user_map.get(uid, uid)}"
    return re.sub(r'<@(U[A-Z0-9]+)>', replace_match, text)

def redact_pii(text: str) -> str:
    """Strips out email addresses, phone numbers, and SSNs from text."""
    if not text:
        return ""
    # Redact email addresses
    text = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '[EMAIL]', text)
    # Redact phone numbers (safer, non-greedy lookbehind pattern)
    text = re.sub(r'(?<!\w)(?:\+?\d{1,4}[-.\s]\(?\d{2,3}\)?[-.\s]\d{3,4}[-.\s]\d{4}\b|\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b)', '[PHONE]', text)
    # Redact SSNs
    text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', text)
    return text

def split_into_sentences(text: str) -> List[str]:
    """Splits a block of text into individual sentences using punctuation boundaries."""
    if not text:
        return []
    # Split by periods, question marks, or exclamation marks followed by whitespace
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]

def parse_ts_to_iso(ts_str: str) -> str:
    """Safely parses a Unix timestamp string or formatted date string to ISO 8601 format."""
    if not ts_str:
        return ""
    try:
        val = float(ts_str)
        return datetime.datetime.utcfromtimestamp(val).isoformat() + "Z"
    except ValueError:
        try:
            # Try parsing formatted date string like '2020-08-03 20:02:29'
            dt = datetime.datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
            return dt.isoformat() + "Z"
        except Exception:
            return ts_str

def load_and_filter_csv(csv_path: str) -> List[Dict[str, Any]]:
    """
    Loads raw messages from CSV and filters out joins, leaves, and short entries.
    Also maps user IDs and redacts PII.
    """
    filtered_messages = []
    if not os.path.exists(csv_path):
        print(f"Ingestion CSV not found: {csv_path}")
        return []
        
    # Load user mappings if users.csv is present
    users_csv = csv_path.replace("messages.csv", "users.csv")
    user_map = load_user_mappings(users_csv)
        
    seen_ts = set()
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = row.get('ts', '')
            subtype = row.get('subtype', '')
            text = row.get('text', '') or ''
            
            # Remove duplicate ts messages
            if ts in seen_ts:
                continue
            seen_ts.add(ts)
            
            # Filter joins/leaves
            if subtype in ['channel_join', 'channel_leave']:
                continue
                
            # Filter short messages (<15 words) or empty messages
            words = text.split()
            if len(words) < 15:
                continue
                
            # Replace user mentions
            text_with_mentions = replace_user_mentions(text, user_map)
                
            # Redact PII
            clean_text = redact_pii(text_with_mentions)
            
            channel = row.get('channel_id', '') or 'unknown_channel'
            user_id = row.get('user', '') or 'unknown_user'
            mapped_user = user_map.get(user_id, user_id)
            
            filtered_messages.append({
                "text": clean_text,
                "user": mapped_user,
                "channel": channel,
                "timestamp": row.get('latest_reply', '') or parse_ts_to_iso(ts),
                "source_id": f"slack://{channel}/{ts}"
            })
            
    return filtered_messages

def run_ingestion_pipeline(csv_path: str, max_messages: int = 200, max_clusters: int = None) -> List[Dict[str, Any]]:
    """
    Runs the complete Phase 1 ingestion pipeline.
    max_messages limits execution size to conserve tokens on Azure during testing.
    max_clusters limits the number of clusters to process to control runtime.
    Returns a list of synthesized page dicts:
    [
        {"page_id": "page_001", "content": "...", "metadata": {...}, "validation": {...}},
        ...
    ]
    """
    print("Step 1: Loading and filtering Slack CSV messages...")
    messages = load_and_filter_csv(csv_path)
    if not messages:
        print("No messages to ingest.")
        return []
        
    # Limit message count for safety
    messages = messages[:max_messages]
    print(f"Loaded {len(messages)} messages for ingestion.")
    
    # Step 2: Split into sentences and map back to metadata
    print("Step 2: Splitting messages into sentences...")
    sentence_records = []
    for msg in messages:
        sentences = split_into_sentences(msg["text"])
        for s in sentences:
            sentence_records.append({
                "text": s,
                "metadata": {
                    "user": msg["user"],
                    "channel": msg["channel"],
                    "timestamp": msg["timestamp"],
                    "source_id": msg["source_id"]
                }
            })
    print(f"Generated {len(sentence_records)} sentences.")
    
    # Step 3: Sentence Classification
    print("Step 3: Classifying sentences into speech acts (CONDITION, PRESCRIPTION, etc.)...")
    cache_path = os.path.join(os.path.dirname(csv_path), "classified_sentences_cache.json")
    loaded_from_cache = False
    
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached_records = json.load(f)
            if len(cached_records) == len(sentence_records):
                print(f"  Loaded {len(cached_records)} classified sentences from cache: {cache_path}")
                sentence_records = cached_records
                loaded_from_cache = True
        except Exception as e:
            print(f"  Warning: Failed to load classification cache: {e}")
            
    if not loaded_from_cache:
        # Batch classification in groups of 25 to reduce API round trips
        batch_size = 25
        sentence_texts = [r["text"] for r in sentence_records]
        classified_types = []
        
        for i in range(0, len(sentence_texts), batch_size):
            batch = sentence_texts[i:i+batch_size]
            print(f"  Classifying batch {i//batch_size + 1}/{-(-len(sentence_texts)//batch_size)}")
            classified_types.extend(classify_sentences(batch))
            
        for r, t in zip(sentence_records, classified_types):
            r["type"] = t
            
        # Save to cache
        try:
            cache_dir = os.path.dirname(cache_path)
            if cache_dir:
                os.makedirs(cache_dir, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(sentence_records, f, indent=2)
            print(f"  Saved {len(sentence_records)} classified sentences to cache: {cache_path}")
        except Exception as e:
            print(f"  Warning: Failed to save classification cache: {e}")
        
    # Step 4: Semantic Clustering
    print("Step 4: Performing local semantic clustering into decision units...")
    clusters = cluster_sentences(sentence_records, similarity_threshold=0.68)
    if max_clusters is not None:
        clusters = clusters[:max_clusters]
    print(f"Grouped sentences into {len(clusters)} clusters.")
    
    # Step 5 & 6: Synthesis and Validation loop
    synthesized_pages = []
    print("Step 5 & 6: Synthesizing and validating pages...")
    for idx, cluster in enumerate(clusters):
        page_index = idx + 1
        print(f"  Processing Cluster {page_index}/{len(clusters)} ({len(cluster)} sentences)...")
        
        sources_list = [item["text"] for item in cluster]
        
        # Synthesis loop with up to 2 re-synthesis attempts on validation failure
        attempts = 0
        max_attempts = 3
        validation_passed = False
        page_content = ""
        validation_result = {}
        feedback = None
        temperature = 0.3
        
        while attempts < max_attempts and not validation_passed:
            attempts += 1
            print(f"    Synthesis attempt {attempts}/{max_attempts}...")
            page_content = synthesize_page(page_index, cluster, feedback=feedback, temperature=temperature)
            
            print("    Validating synthesized page...")
            validation_result = validate_page(sources_list, page_content)
            validation_passed = validation_result.get("validation_passed", False)
            
            if not validation_passed:
                reason = validation_result.get("reason", "Unknown")
                print(f"    Validation failed. Reason: {reason}")
                
                # Analyze validation scores to build helpful feedback and lower temperature
                cov = validation_result.get("proposition_coverage", 1.0)
                hal = validation_result.get("hallucination_rate", 0.0)
                comp = validation_result.get("completeness_score", 10)
                
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
                    temperature = 0.2  # Restrict creativity for precision
                    
                feedback = "\n".join(feedback_parts)
                
        status = "APPROVED" if validation_passed else "DRAFT"
        print(f"    Page {page_index:03d} finalized with status: {status}")
        
        # Parse YAML frontmatter, inject validation scores, and serialize back to markdown
        metadata, body = parse_markdown_with_frontmatter(page_content)
        metadata["id"] = f"page_{page_index:03d}"
        metadata["status"] = status
        metadata["synthesis_validation"] = {
            "proposition_coverage": validation_result.get("proposition_coverage", 0.0),
            "hallucination_rate": validation_result.get("hallucination_rate", 1.0),
            "completeness_score": validation_result.get("completeness_score", 1),
            "validation_passed": validation_passed,
            "validated_at": datetime.datetime.utcnow().isoformat() + "Z"
        }
        
        final_page_content = serialize_markdown_with_frontmatter(metadata, body)
        
        synthesized_pages.append({
            "page_id": f"page_{page_index:03d}",
            "content": final_page_content,
            "status": status,
            "validation": validation_result,
            "sources": sources_list
        })
        
    return synthesized_pages

if __name__ == '__main__':
    # Local dry run path
    csv_path = r"C:\Users\dell\.gemini\antigravity\brain\99a9c7c3-962c-4b53-b42e-876755f250f8\scratch\messages.csv"
    try:
        pages = run_ingestion_pipeline(csv_path, max_messages=5)
        print(f"Ingested {len(pages)} pages successfully.")
    except Exception as e:
        print("Dry run error:", e)
