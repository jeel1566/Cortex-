"""
alias_resolver.py — Two-phase user alias extraction.

Phase 1: Regex scan for self-introduction patterns (free, fast)
Phase 2: LLM validation for ambiguous candidates (targeted, cheap)

Produces a persistent alias map: {user_id: [official_name, alias1, alias2, ...]}
"""

import os
import re
import json
from typing import Dict, List, Set, Any

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from app.llm.kimi import get_kimi_client


# ── Phase 1: Regex Patterns ──────────────────────────────────────────

INTRO_PATTERNS = [
    # "I'm Brandon" / "I am Brandon"
    r"(?:I'm|I am)\s+([A-Z][a-z]{2,})",
    # "my name is Brandon" / "name's Brandon"
    r"(?:my name is|name's)\s+([A-Z][a-z]{2,})",
    # "call me Bub" / "known as Boba"
    r"(?:call me|known as|goes by|aka)\s+[\"']?([A-Z]?[a-z]{2,})[\"']?",
    # "friends call me Bubba"
    r"(?:friends call me|everyone calls me|people call me)\s+[\"']?([A-Z]?[a-z]{2,})[\"']?",
    # "nickname is Bub"
    r"(?:nickname is|nick is)\s+[\"']?([A-Z]?[a-z]{2,})[\"']?",
]

# Words that match intro patterns but aren't names
FALSE_POSITIVE_WORDS = {
    "fine", "good", "here", "back", "sorry", "sure", "happy", "excited",
    "working", "trying", "looking", "wondering", "thinking", "using",
    "new", "interested", "curious", "available", "done", "ready",
    "not", "also", "just", "still", "currently", "actually",
    "glad", "afraid", "able", "unable", "going", "getting",
    "having", "doing", "running", "testing", "building", "deploying",
}


def _regex_extract_aliases(
    messages: List[Dict[str, Any]],
    user_map: Dict[str, str],
) -> Dict[str, Set[str]]:
    """Phase 1: Fast regex scan over all messages."""
    alias_candidates: Dict[str, Set[str]] = {}
    for msg in messages:
        uid = msg.get("user", "").split(" [")[-1].rstrip("]")
        text = msg.get("text", "")
        if not uid or not text:
            continue
        for pattern in INTRO_PATTERNS:
            for name in re.findall(pattern, text, re.IGNORECASE):
                clean = name.strip().capitalize()
                official = user_map.get(uid, "").lower()
                if clean.lower() not in FALSE_POSITIVE_WORDS and clean.lower() not in official and len(clean) >= 3:
                    alias_candidates.setdefault(uid, set()).add(clean)
    return alias_candidates


# ── Phase 2: LLM Validation ─────────────────────────────────────────

VALIDATION_PROMPT = """You are a highly precise linguistic annotator. Your goal is to analyze user Slack messages and verify if the candidate aliases refer to the same person.

Official Directory Name: {official_name}
Candidate Aliases: {candidates}

<messages>
{messages}
</messages>

<instructions>
1. Check if the candidate aliases are indeed used by the sender to refer to themselves (e.g. self-introduced names, common nicknames).
2. Look for other self-referred names in the messages that were not in the candidates list.
3. Respond ONLY with a valid JSON object matching the schema below. Do not include markdown blocks or extra text.
</instructions>

<schema>
{{
  "confirmed_aliases": ["genuine aliases/nicknames confirmed from the text"],
  "rejected": ["false positive matches"],
  "additional": ["newly found names/nicknames used by this person"]
}}
</schema>"""


def _llm_validate_aliases(
    user_id: str,
    official_name: str,
    candidates: Set[str],
    user_messages: List[str],
) -> Set[str]:
    """
    Phase 2: LLM validates ambiguous candidates and finds missed ones.
    Only called when regex found candidates — not for every user.
    """
    client = get_kimi_client()

    # Limit to 10 messages to control token cost
    sample_messages = user_messages[:10]
    messages_text = "\n".join(f"- {m}" for m in sample_messages)

    prompt = VALIDATION_PROMPT.format(
        official_name=official_name,
        candidates=", ".join(candidates),
        messages=messages_text,
    )

    try:
        response = client.chat_completion(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=256,
        )
        # Try to parse JSON from response
        response_clean = response.strip().strip("`").strip()
        if response_clean.startswith("json"):
            response_clean = response_clean[4:].strip()

        result = json.loads(response_clean)
        confirmed = set(result.get("confirmed_aliases", []))
        additional = set(result.get("additional", []))
        return confirmed | additional
    except Exception as e:
        print(f"  [AliasResolver] LLM validation failed for {user_id}: {e}")
        # Fallback: trust the regex candidates
        return candidates


# ── Main Entry Point ─────────────────────────────────────────────────

def resolve_aliases(
    messages: List[Dict[str, Any]],
    user_map: Dict[str, str],
    use_llm_validation: bool = True,
) -> Dict[str, List[str]]:
    """
    Build a complete alias map for all users.

    Args:
        messages: List of message dicts with 'user' and 'text' fields
        user_map: Official {user_id: "Name [UserID]"} from users.csv
        use_llm_validation: If True, validates regex candidates with LLM

    Returns:
        {user_id: [official_name, alias1, alias2, ...]}
    """
    # Phase 1: Regex scan
    print("  [AliasResolver] Phase 1: Regex extraction...")
    candidates = _regex_extract_aliases(messages, user_map)
    print(f"  [AliasResolver] Found {sum(len(v) for v in candidates.values())} "
          f"candidate aliases for {len(candidates)} users")

    # Build per-user message index (needed for Phase 2)
    user_messages: Dict[str, List[str]] = {}
    if use_llm_validation and candidates:
        for msg in messages:
            uid = msg.get("user", "").split(" [")[-1].rstrip("]")
            if uid in candidates:
                user_messages.setdefault(uid, []).append(msg.get("text", ""))

    # Phase 2: LLM validation (only for users with candidates)
    alias_map: Dict[str, List[str]] = {}
    for uid, display in user_map.items():
        if uid in candidates:
            official = display.split(" [")[0]
            if use_llm_validation:
                print(f"  [AliasResolver] Phase 2: Validating {uid} ({official}) — candidates: {candidates[uid]}")
                confirmed = _llm_validate_aliases(uid, official, candidates[uid], user_messages.get(uid, []))
                alias_map[uid] = [official] + sorted(confirmed)
            else:
                alias_map[uid] = [official] + sorted(candidates[uid])

    print(f"  [AliasResolver] Final alias map: {len(alias_map)} users with aliases")
    return alias_map


def save_alias_map(alias_map: Dict[str, List[str]], output_path: str) -> None:
    """Persist alias map to JSON for query-time use."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(alias_map, f, indent=2)
    print(f"  [AliasResolver] Saved alias map to {output_path}")


def load_alias_map(path: str) -> Dict[str, List[str]]:
    """Load alias map from JSON file."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  [AliasResolver] Error loading alias map: {e}")
        return {}
