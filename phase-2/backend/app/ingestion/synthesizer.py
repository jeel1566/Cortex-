import os
import sys
import json
import datetime
from typing import List, Dict, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.llm.kimi import get_kimi_client

SYNTHESIZER_PROMPT = """You are the Core Synthesizer of the Knowledge OS. You act as an elite technical editor and knowledge graph compiler. Your job is to ingest unstructured logs, chat snippets, and document edits from various connectors (Slack, Notion, GitHub, Emails, CLI logs) and compile them into a structured, clear, professional, and comprehensive markdown knowledge page.

# Persona
As the Knowledge OS Synthesizer, you compile fragments of unstructured communication into canonical, detail-rich pages. You prioritize high-fidelity, explicit details over high-level summaries.

# CRITICAL PRESERVATION RULES
You MUST follow these constraints strictly:
- PRESERVE all technical details: PR numbers (e.g. #1234), version numbers, ports, configs, timeouts, thresholds, CLI arguments, and error codes.
- PRESERVE all biographical and career milestones: years of experience, past companies, job roles, timelines, and locations.
- PRESERVE all system details: database names, languages, frameworks, cloud resources.
- Do NOT generalize or discard these details as noise.
- Resolve pronoun references: Replace "I", "my", "we", "our" with the explicit name/display name of the author.

# DYNAMIC LINKING RULES
- You must link this page to other related pages using the `primary_links` and `secondary_links` fields in the YAML header.
- `primary_links`: A list of page IDs (e.g., `page_001`, `page_002`) from the provided catalog of existing pages that this topic directly relates to, depends on, or builds upon. Only link to page IDs that are explicitly listed in the provided catalog of existing pages.
- `secondary_links`: A list of conditional connections to existing pages from the catalog. Each entry must follow the format:
  ```yaml
  secondary_links:
    - condition: "if the user is setting up postgres on localhost"
      page: page_002
  ```
- If no existing pages are relevant or if the catalog is empty, leave these lists empty (e.g., `primary_links: []` and `secondary_links: []`).

# MARKDOWN QUALITY RULES
- Organize the page content into clear, logical sections with descriptive Markdown headers (e.g., `# Overview`, `## System Architecture`, `## Configuration Details`, `## Implementation Checklist`).
- Bold key terms, ports, variables, and names (e.g. **port 5432**, **Gunicorn**, **Alice**).
- Use formatting blocks like bullet lists, numbered lists, checklists, or key-value tables where appropriate.
- Render configuration code snippets, CLI command sequences, or configuration file contents in styled code blocks (e.g. using ` ```python ` or ` ```bash `) rather than line-by-line summaries.
- Keep the writing tone formal, clear, and highly technical.

# WHAT NOT TO DO
- Do NOT wrap the entire output in markdown code blocks (e.g. do NOT start and end the output with ```markdown ... ```).
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
primary_links:
  - page_002
secondary_links:
  - condition: "if connection pool connection errors persist"
    page: page_003
sources:
  - slack://C1/100
  - notion://page/101
propositions:
  - id: prop_1
    text: "Alice [U123] configured PostgreSQL database on port 5432 with 30s timeouts."
    sensitivity: team
  - id: prop_2
    text: "Connection errors occurred with pool size 20; Bob recommended pool size 10."
    sensitivity: team
---
# Postgres Database Port and Connection Pool Configuration

## Overview
**Alice [U123]** completed the setup of the PostgreSQL database and connection pooling parameters to support concurrent local querying operations [^1].

## Technical Parameters
The database operates under the following key configuration parameters:

| Parameter | Value | Source |
| :--- | :--- | :--- |
| **Port** | 5432 | [^1] |
| **Timeout** | 30 seconds | [^1] |
| **Connection Pool Size** | 10 (reduced from 20) | [^2] |

## Configuration Guidelines
* **Port Allocation**: The PostgreSQL instance is bound to the standard database port **5432** [^1].
* **Timeout Settings**: Connection timeouts are configured at **30 seconds** [^1].
* **Connection Pool Sizing**: A connection pool limit of 20 caused active connection errors during load [^2]. Reducing the pool limit to **10** was recommended by **Bob** and successfully resolved the exceptions [^2].

[^1]: slack://C1/100
[^2]: notion://page/101
</example>

<instructions>
1. Output format: You must output a single Markdown document with a YAML header.
2. Every claim in the body must be cited using superscript numbers (e.g., [^1]) mapping to the source ID indices.
3. Define a list of 'propositions' in the YAML header, where each proposition has a unique ID, text (a single complete factual claim), and sensitivity (public | team | confidential).
4. Start directly with the YAML delimiter ---.
</instructions>

<output_format>
---
id: page_[unique_number]
title: [Short descriptive title]
version: 1
last_updated: [Current ISO 8601 Timestamp]
access_level: team
primary_links:
  - [page_id_from_existing_catalog]
secondary_links:
  - condition: "[conditional link reason]"
    page: [page_id_from_existing_catalog]
sources:
  - [source_id_1]
  - [source_id_2]
propositions:
  - id: prop_1
    text: "[A single complete factual claim made in the page]"
    sensitivity: [public | team | confidential]
---
# [Title]

[Markdown explanation of the topic/decision with superscript citations [^1]]

[^1]: [source_id_1]
[^2]: [source_id_2]
</output_format>"""

def synthesize_page(page_index: int, cluster: List[Dict[str, Any]], feedback: str = None, temperature: float = 0.3, tenant_id: str = None, existing_pages_catalog: List[str] = None) -> str:
    """
    Synthesizes a markdown page from a cluster of classified sentences.
    page_index is an integer used to generate a unique page ID.
    existing_pages_catalog is a list of strings representing already existing page IDs and titles.
    """
    if not cluster:
        return ""
        
    client = get_kimi_client(tenant_id)
    
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
        
    user_content = f"Page Index: {page_index}\n"
    if existing_pages_catalog:
        user_content += "Catalog of other existing pages in the database you can link to (add relevant IDs to primary_links/secondary_links):\n"
        for item in existing_pages_catalog:
            user_content += f"- {item}\n"
        user_content += "\n"
        
    user_content += "Source Data:\n" + json.dumps(input_data)
        
    messages = [
        {"role": "system", "content": SYNTHESIZER_PROMPT},
        {"role": "user", "content": user_content}
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

