# Cortex V3.0: Unified Action & Security Specification

This specification outlines the architectural addition to the Cortex Knowledge OS, moving it from a passive document graph (the "Book") to an active execution runtime (the "Robot Chef").

---

## 1. The Core Triad Architecture

Cortex V3.0 coordinates three distinct cognitive agents working as a single operating system kernel:

1. **The Reader (The Researcher)**:
   - Ingests raw data streams (Slack, Notion, specs).
   - Indexes text vectors in HNSW and maps entity relations in pgvector/SQLite.
   - Handles BFS Graph + HNSW vector hybrid query routing in <200ms.
2. **The Dynamic Skill Maker (The Architect)**:
   - Evaluates the context retrieved by the Reader.
   - Synthesizes clean guidelines (`SKILL.md`) that map out standard operating procedures, required inputs, and safety constraints.
3. **The Dynamic Tool Maker (The Engineer)**:
   - Takes the rules from the Skill Maker and writes python/javascript code (`scripts/*.py`) to automate the APIs or commands.
   - Runs validation tests (e.g. checking syntax and compilation).
   - Saves scripts to the tenant Git repository and references them in the Skill page's `executable_skills` YAML frontmatter.

---

## 2. Dynamic Tool Sandbox Execution

When a client agent (e.g., Cursor, Claude Code) triggers an action, the Cortex server hosts and executes the tool in an isolated sandbox.

### Execution Lifecycle
1. **Tool Lease**: When a page is returned, Cortex includes the `executable_skills` schemas in the JSON response.
2. **Call Dispatch**: The client agent calls `POST /v1/execute/{page_id}/{tool_name}` with parameters.
3. **Auth Check**: Cortex decodes the agent's JWT, verifies L0-L5 authority ceilings and domain-scope constraints.
4. **Subprocess Isolation**: Cortex spawns the script in a sandboxed subprocess (`subprocess.run`), injecting credentials securely, capping execution time at 10 seconds, and returning the output.

---

## 3. Secure Hybrid Credential Keyring

To facilitate both autonomous background syncs and highly sensitive manually-triggered commands, Cortex implements a two-tier keyring:

### A. Persistent Credentials (Encrypted & Stored)
* **Usage**: Sync integrations (Slack OAuth, Notion Polling).
* **Security**: Encrypted via **AES-256-GCM** inside the tenant configuration SQLite table. The master key (`CORTEX_MASTER_KEY`) resides strictly in server RAM and is never stored on disk.

### B. Ephemeral Credentials (Session-Only)
* **Usage**: High-risk actions (DB Migrations, Server SSH).
* **Security**: Attached via HTTPS headers (`X-Ephemeral-Key`) by the user. Kept in the memory space of the sandbox process, used once, and instantly purged from RAM when execution terminates.

### C. Dynamic Escalation
* If a key is missing or expired, Cortex returns `401 Unauthorized` with a `CREDENTIALS_REQUIRED` code and the parameter requirements. The coding agent catches this and prompts the user to input the missing key on-the-fly.
