# Cortex V3.0: Dynamic Actions and Security Architecture Summary

This document summarizes the approved design decisions for Cortex V3.0, moving from a passive RAG database to an active, secure Knowledge OS.

---

## 1. Unified Agent Triad (Computation Layer)

Cortex V3.0 coordinates three active systems to bridge the gap between knowing and doing:

```
[Raw Data] ---> 1. THE READER (Retrieves Graph Context)
                      │
                      ▼
                2. DYNAMIC SKILL MAKER (Drafts Guidelines/SKILL.md)
                      │
                      ▼
                3. DYNAMIC TOOL MAKER (Writes/Validates Python Scripts)
                      │
                      ▼
                [Tenant Git Repository] (Scripts + Pages Committed)
```

1. **The Reader**: Evaluates raw data and builds the semantic graph.
2. **The Dynamic Skill Maker**: Synthesizes structured guideline cards and registers operational rules.
3. **The Dynamic Tool Maker**: Writes the actual code (`scripts/*.py`) to perform the actions and lists them as `executable_skills` in the page's YAML frontmatter.

---

## 2. Server-Side Sandbox Execution

All dynamic tools must execute inside a secure server-side sandbox, never on the client agent's local environment.

* **Tool Discovery**: Available tools are leased to the agent dynamically in the page headers.
* **API Endpoints**: The agent calls `POST /v1/execute/{page_id}/{tool_name}` with JSON parameters.
* **Sandbox Security**: Cortex runs the code in an isolated subprocess (`subprocess.run`), monitors execution limits (10s timeout), validates user JWT authority level (L0-L5), and returns the results.

---

## 3. Secure Hybrid Keyring

To facilitate secure background processes (like 5-minute syncs) and sensitive operations (like migrations), Cortex utilizes a two-tier key management system:

### A. Persistent Keys (Encrypted)
* **Scope**: Sync integrations (Slack, Notion, Github).
* **Storage**: Encrypted using **AES-256-GCM** inside the tenant configuration SQLite table. Decryption keys are loaded into RAM strictly at server startup via environment variables.

### B. Ephemeral Keys (Session-Only)
* **Scope**: Sensitive commands (Server SSH, database drop/migrations).
* **Storage**: Passed in HTTPS request headers (`X-Ephemeral-Key`), utilized inside the subprocess memory space, and instantly purged from RAM when the process exits.

### C. Escalation
* If a tool request lacks a key, Cortex returns a `401 Credentials Required` status, which prompts the client agent to collect the credential from the developer on-the-fly.
