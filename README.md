# Cortex Knowledge OS

Cortex is an enterprise-grade corporate Knowledge OS designed to ingest unstructured company communications (such as Slack logs and Notion pages), filter and redact PII, classify speech acts, cluster them into decision units, and synthesize version-controlled, canonical markdown knowledge pages. 

The repository contains two key development phases:
1. **[Phase 1](file:///D:/Cortex/phase-1)**: Single-tenant command-line ingestion compiler and RAG benchmark evaluation suite (configured for local Ollama and Codex server setups).
2. **[Phase 2](file:///D:/Cortex/phase-2)**: Secure, production-ready multi-tenant Knowledge OS featuring physical isolation, Git-backed versioning, Clerk JWT authentication, background ingestion queues, a Notion sync connector, and a beautiful Next.js admin frontend.

---

## 🏗️ Repository Architecture

Cortex is organized cleanly into modular folders:

```text
Cortex/
├── phase-1/                     # Single-tenant RAG benchmark pipeline
│   ├── app/                     # Local LLM client, vector index, and search engine
│   ├── data/                    # Portable csv datasets (messages.csv, users.csv)
│   ├── eval/                    # Ground truth queries and baseline reports
│   └── tests/                   # Ingestion and synthesis unit tests
│
├── phase-2/                     # Production-ready multi-tenant portal
│   ├── backend/                 # FastAPI service with tenant isolated SQLite/Git
│   └── frontend/                # Next.js 14 corporate admin workspace
│
├── docs/                        # Specifications and design plans
│   ├── markdown/                # PRD, TRD, UI/UX, and onboarding documents
│   └── provider.md              # Codex CLI websocket interface specifications
│
├── README.md                    # This overview guide
├── LLM_SETUP_GUIDE.md           # Local Ollama & Codex manual setup instructions
└── walkthrough.md               # Quickstart checklist for Ollama setup
```

---

## 🚀 Key Features

* **Multi-Tenant Physical Isolation**: Completely isolates SQLite databases (`metadata.db`), Git repositories (under `repo/`), and vector indices (`vector_index.json`) for each tenant.
* **Onboarding & Configuration Gates**: Intercepts unconfigured or first-time tenants with a modern **Onboarding Setup Wizard** to configure their LLM provider (Ollama, Web API, or Codex) dynamically before accessing the app.
* **Sleek Admin Portal**: Interactive Next.js 14 interface featuring an **Admin Approval Inbox** to review page drafts and a **Knowledge Explorer** for page searching, markdown reading, and clearance auditing.
* **Git-backed Audit Trail**: Programmatic commits made via `GitPython` tracking every ingestion run, modification, or feedback-triggered re-synthesis with full history regression.
* **Clerk JWT Authentication**: Security framework validating bearer tokens and mapping claims to L0-L5 authority levels. Includes a mock pass-through mode for developer speed.
* **Ingestion Worker & Connectors**: Asynchronous background queue executing tasks (Immediate, Standard, Background) and polling active Notion integrations every 5 minutes.

---

## 🛠️ Setup & Quickstart

Before starting, configure a local LLM or API keys. Read the [LLM Setup Guide](file:///D:/Cortex/LLM_SETUP_GUIDE.md) and [Walkthrough Guide](file:///D:/Cortex/walkthrough.md) for details on installing Ollama or the Codex App Server.

### Phase 1: Local Ingestion & Evaluation Benchmark
1. Navigate to the Phase 1 folder:
   ```bash
   cd phase-1
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the Slack ingestion pipeline:
   ```bash
   python ingest_slack.py
   ```
5. Run the evaluation suite:
   ```bash
   python run_cortex_eval.py
   ```

---

### Phase 2: Multi-Tenant Platform

#### 1. Configure Environments
Create a `.env` file in `phase-2/backend/` and `phase-2/frontend/.env.local` to toggle authorization keys.
* For local dev mode, you can leave Clerk keys blank. The systems will fall back to safe pass-through mock authentications (representing tenant_a L5 admin).
* Default LLM settings on backend startup default to `not_configured`, letting you choose your model provider dynamically during onboarding.

#### 2. Start the FastAPI Backend
1. Navigate to the backend directory:
   ```bash
   cd phase-2/backend
   pip install -r requirements.txt
   ```
2. Run the server:
   ```bash
   python run_backend.py
   ```
   * The API starts at `http://localhost:8000`.
   * Swagger docs: `http://localhost:8000/docs`.
   * Prometheus metrics: `http://localhost:8000/metrics`.

#### 3. Start the Next.js Frontend
1. Navigate to the frontend directory:
   ```bash
   cd phase-2/frontend
   npm install
   ```
2. Start the development server:
   ```bash
   npm run dev
   ```
3. Open `http://localhost:3000` in your web browser. Login or click Sign In (in mock mode), select your LLM provider in the onboarding wizard, and enjoy!

---

## 🧪 Testing

Both development phases contain complete unit and integration test suites.

* **Phase 1 Ingestion Tests**:
  ```bash
  cd phase-1
  python -m unittest discover -s tests
  ```
* **Phase 2 Tenant Isolation & Ingestion Pipeline Tests**:
  ```bash
  cd phase-2/backend
  python -m unittest discover -s tests
  ```

---

## 📖 In-Depth Specifications & Architectural Guides
* **Onboarding & Switcher Design**: [10-cortex-onboarding-and-settings.md](file:///D:/Cortex/docs/markdown/10-cortex-onboarding-and-settings.md)
* **Core Product Requirement Document (PRD)**: [01-cortex-prd.md](file:///D:/Cortex/docs/markdown/01-cortex-prd.md)
* **Technical Requirement Document (TRD)**: [02-cortex-trd.md](file:///D:/Cortex/docs/markdown/02-cortex-trd.md)
* **System Architecture Overview**: [07-cortex-architecture.md](file:///D:/Cortex/docs/markdown/07-cortex-architecture.md)
