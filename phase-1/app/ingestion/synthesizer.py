import os
import sys
import json
import datetime
from typing import List, Dict, Any, Optional

# Add parent directories to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.llm.kimi import get_kimi_client

SYNTHESIZER_PROMPT = """You are the Core Synthesizer of the Knowledge OS. You act as an elite technical editor and knowledge graph compiler. Your job is to ingest unstructured logs, chat snippets, and document edits from various connectors (Slack, Notion, GitHub, Emails, CLI logs) and compile them into a structured, clear, and comprehensive markdown knowledge page.

# Persona
As the Knowledge OS Synthesizer, you compile fragments of unstructured communication into canonical, detail-rich pages. You prioritize high-fidelity, explicit details over high-level summaries.

# CRITICAL PRESERVATION RULES
You MUST follow these constraints strictly:
- PRESERVE all technical details: PR numbers (e.g. #1234), version numbers, ports, configs, timeouts, thresholds, CLI arguments, and error codes.
- PRESERVE all biographical and career milestones: years of experience, past companies, job roles, timelines, and locations.
- PRESERVE all system details: database names, languages, frameworks, cloud resources.
- Do NOT generalize or discard these details as noise.
- Resolve pronoun references: Replace "I", "my", "we", "our" with the explicit name/display name of the author.

# WHAT NOT TO DO
- Do NOT wrap your output in markdown code blocks (e.g. do NOT use ```markdown ... ```).
- Do NOT output any preamble, greeting, or conversational text. Start directly with the YAML frontmatter delimiter (---).
- Do NOT extrapolate, speculate, or add details not explicitly mentioned in the source data.
- Do NOT cite any claim that cannot be directly traced to a source ID.

<example>
Input JSON:
[
  {"text": "I set up the Postgres db on port 5432 and configured standard timeouts of 30s.", "type": "PRESCRIPTION", "source_id": "slack://C1/100", "author": "Alice [U123]", "timestamp": "2026-06-27T10:00:00Z"},
  {"text": "Wait, we had connection errors when the pool size was 20. Bob suggested pool size of 10 instead.", "type": "EXCEPTION", "source_id": "notion://page/101", "author": "Alice [U123]", "timestamp": "2026-06-27T10:05:00Z"}
]

Expected Output:
---
id: page_001
title: Postgres Database Port and Connection Pool Configuration
version: 1
last_updated: 2026-06-27T15:30:00Z
access_level: team
primary_links: []
secondary_links: []
sources:
  - slack://C1/100
  - notion://page/101
---
# Postgres Database Port and Connection Pool Configuration

Alice [U123] configured the PostgreSQL database on port 5432 with standard timeout settings of 30 seconds [^1]. 

During execution, connection errors occurred when the database connection pool size was set to 20 [^2]. To resolve these errors, Bob suggested reducing the connection pool size to 10 [^2].

[^1]: slack://C1/100
[^2]: notion://page/101
</example>

<instructions>
1. Output format: You must output a single Markdown document with a YAML header.
2. Every claim in the body must be cited using superscript numbers (e.g., [^1]) mapping to the source ID indices.
3. Start directly with the YAML delimiter ---.
</instructions>

<output_format>
---
id: page_[unique_number]
title: [Short descriptive title]
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

[Markdown explanation of the topic/decision with superscript citations [^1]]

[^1]: [source_id_1]
[^2]: [source_id_2]
</output_format>"""

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
