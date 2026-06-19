import os
import sys
import json
import datetime
from typing import List, Dict, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.llm.kimi import get_kimi_client

SYNTHESIZER_PROMPT = """
You are an expert technical writer and knowledge engineer.
Your task is to take a cluster of sentences extracted from company Slack logs and synthesize them into a single, cohesive, canonical knowledge page in Markdown format with a YAML frontmatter header.

Input:
A JSON list of source message objects. Each object contains:
- "text": The message or sentence content.
- "type": The speech-act type (CONDITION, PRESCRIPTION, PROCEDURE, EXCEPTION, OUTCOME).
- "source_id": A unique identifier for the source (e.g. "slack://C123/1593710973").
- "author": The user ID of the sender.
- "timestamp": The timestamp.

Output:
You must output a single Markdown document with a YAML header.
The YAML header MUST define a list of 'propositions' extracted from the text, where each proposition is tagged with a sensitivity level (public, team, or confidential).

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
propositions:
  - id: prop_1
    text: "[A single complete factual claim made in the page]"
    sensitivity: [public | team | confidential]
---
# [Title]

[A synthesized, clear explanation of the policy, decision, or procedure. Use Markdown formatting like lists or headers where appropriate.]
Every factual claim you write MUST be backed by a source. You MUST append a citation superscript (e.g. [^1]) to the end of sentences that represent claims, mapped to the index of the source in the YAML sources list.

DO NOT output any extra explanation. Start directly with the opening '---' of the YAML block.
"""

def synthesize_page(page_index: int, cluster: List[Dict[str, Any]], feedback: str = None, temperature: float = 0.3) -> str:
    """
    Synthesizes a markdown page from a cluster of classified sentences.
    page_index is an integer used to generate a unique page ID.
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
        
    messages = [
        {"role": "system", "content": SYNTHESIZER_PROMPT},
        {"role": "user", "content": f"Page Index: {page_index}\nSource Data:\n" + json.dumps(input_data)}
    ]
    if feedback:
        messages.append({
            "role": "user",
            "content": f"Based on validation of your previous synthesis attempt, please apply the following corrections:\n{feedback}"
        })
        
    try:
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
propositions:
  - id: prop_1
    text: Auto-synthesized fallback page details
    sensitivity: team
---
# {title}

Auto-synthesized fallback page.
The following points were discussed:
"""
        for i, item in enumerate(cluster):
            fallback_content += f"- {item['text']} [^{i+1}]\n"
            
        return fallback_content
