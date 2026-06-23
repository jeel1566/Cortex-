import os
import sys
import json
import datetime
from typing import List, Dict, Any, Optional

# Add parent directories to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.llm.kimi import get_kimi_client

SYNTHESIZER_PROMPT = """
You are an expert technical writer and knowledge engineer.
Your task is to take a cluster of sentences extracted from company Slack logs and synthesize them into a single, cohesive, canonical knowledge page in Markdown format with a YAML frontmatter header.

CRITICAL PRESERVATION RULES — You MUST follow these:
1. PRESERVE all specific numbers: PR numbers (#1234), version numbers, port numbers, timeout values, worker counts, and any numeric configuration.
2. PRESERVE all URLs and links exactly as they appear.
3. PRESERVE all biographical details: years of experience, previous companies, job titles, locations, career timelines.
4. PRESERVE all technology names: databases, languages, frameworks, cloud providers.
5. PRESERVE all command-line flags, error codes, and tracebacks.
6. PRESERVE all user names and aliases. If a user introduces themselves with a name different from their display name, note BOTH names.
7. When a user says "I" or "my", explicitly attribute the statement to that user by name in the synthesized text.

DO NOT summarize away details as "noise". Every specific fact matters.

Input:
A JSON list of source message objects. Each object contains:
- "text": The message or sentence content.
- "type": The speech-act type (CONDITION, PRESCRIPTION, PROCEDURE, EXCEPTION, OUTCOME).
- "source_id": A unique identifier for the source (e.g. "slack://C123/1593710973").
- "author": The user ID of the sender.
- "timestamp": The timestamp.

Output:
You must output a single Markdown document with a YAML header.
The output format MUST be:
---
id: page_[unique_number]
title: [A short, descriptive title of the topic]
version: 1
last_updated: [Current ISO 8601 Timestamp]
access_level: team
primary_links: []
secondary_links: []
sources:
  - [source_id_1]
  - [source_id_2]
---
# [Title]

[A synthesized, clear explanation of the policy, decision, or procedure. Use Markdown formatting like lists or headers where appropriate.]
Every factual claim you write MUST be backed by a source. You MUST append a citation superscript (e.g. [^1]) to the end of sentences that represent claims, mapped to the index of the source in the YAML sources list.

At the very bottom of the document body, you MUST include standard Markdown footnote definitions mapping each superscript back to its source ID. For example:
[^1]: slack://C123/1593710973
[^2]: slack://C123/1593710984

DO NOT output any extra explanation. Start directly with the opening '---' of the YAML block.
"""

def synthesize_page(page_index: int, cluster: List[Dict[str, Any]], feedback: str = None, temperature: float = 0.3, alias_map: Optional[Dict[str, List[str]]] = None) -> str:
    """
    Synthesizes a markdown page from a cluster of classified sentences.
    page_index is an integer used to generate a unique page ID.
    alias_map is an optional {user_id: [name1, name2, ...]} dict for alias injection.
    """
    if not cluster:
        return ""
        
    client = get_kimi_client()
    
    # Format input payload
    input_data = []
    for item in cluster:
        input_data.append({
            "text": item["text"],
            "type": item.get("type", "PRESCRIPTION"),
            "source_id": item.get("metadata", {}).get("source_id", "slack://unknown"),
            "author": item.get("metadata", {}).get("user", "unknown_user"),
            "timestamp": item.get("metadata", {}).get("timestamp", "")
        })
    
    # Build alias context for users in this cluster
    alias_context = ""
    if alias_map:
        cluster_users = set(item.get("metadata", {}).get("user", "") for item in cluster)
        relevant_aliases = {}
        for user_display in cluster_users:
            uid = user_display.split(" [")[-1].rstrip("]")
            if uid in alias_map:
                relevant_aliases[user_display] = alias_map[uid]
        
        if relevant_aliases:
            alias_lines = []
            for display, names in relevant_aliases.items():
                alias_lines.append(f"- {display} is also known as: {', '.join(names)}")
            alias_context = (
                "\n\nUSER ALIAS INFORMATION (these names all refer to the same person):\n"
                + "\n".join(alias_lines)
                + "\n\nWhen writing about these users, use their most commonly "
                  "self-introduced name and note aliases. When a user says 'I' or 'my', "
                  "attribute it to ALL their known names."
            )
        
    messages = [
        {"role": "system", "content": SYNTHESIZER_PROMPT},
        {"role": "user", "content": f"Page Index: {page_index}\n{alias_context}\nSource Data:\n" + json.dumps(input_data)}
    ]
    if feedback:
        messages.append({
            "role": "user",
            "content": f"Based on validation of your previous synthesis attempt, please apply the following corrections:\n{feedback}"
        })
        
    try:
        # Call Kimi client
        page_content = client.chat_completion(messages, temperature=temperature, max_tokens=1024)
        return page_content.strip()
    except Exception as e:
        print(f"Synthesizer error: {e}")
        # Return fallback stub page if synthesis fails
        sources_list = list(set([item.get("metadata", {}).get("source_id", "slack://unknown") for item in cluster]))
        sources_yaml = "\n".join([f"  - {src}" for src in sources_list])
        title = f"Synthesized Topic {page_index}"
        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        
        fallback_content = f"""---
id: page_{page_index:03d}
title: {title}
version: 1
last_updated: {timestamp}
access_level: team
primary_links: []
secondary_links: []
sources:
{sources_yaml}
---
# {title}

Auto-synthesized fallback page.
The following points were discussed:
"""
        for i, item in enumerate(cluster):
            fallback_content += f"- {item['text']} [^{i+1}]\n"
            
        # Add fallback footnote definitions
        fallback_content += "\n"
        for i, src in enumerate(sources_list):
            fallback_content += f"[^{i+1}]: {src}\n"
            
        return fallback_content

if __name__ == '__main__':
    # Simple test run with dummy data
    test_cluster = [
        {
            "text": "Max started the Superset project in 2015 while at Airbnb.",
            "type": "OUTCOME",
            "metadata": {"source_id": "slack://C1/123", "user": "U123", "timestamp": "2020-07-02"}
        },
        {
            "text": "Erik is a full stack engineer at Airbnb and a PMC member for Superset.",
            "type": "OUTCOME",
            "metadata": {"source_id": "slack://C1/456", "user": "U456", "timestamp": "2020-07-02"}
        }
    ]
    try:
        page = synthesize_page(1, test_cluster)
        print("Synthesized Page:\n", page)
    except Exception as e:
        print("Expected mock failure:", e)
