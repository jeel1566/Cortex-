# Cortex Knowledge OS — Phase 2 Multi-Tenant Platform

This directory contains the production-ready multi-tenant **Cortex Knowledge OS** implementation.

---

## 🛠️ Tech Stack & Key Features

1. **Physical Tenant Isolation**: Separate SQLite databases (`metadata.db`), separate Git repositories (under `repo/`), and separate vector indices (`vector_index.json`) per tenant.
2. **Git-backed Versioning**: Programmatic commits made via `GitPython` tracking every ingestion run, modification, or user feedback-triggered re-synthesis.
3. **Clerk Token Auth & Clearance levels**: Security checks mappings token claims to L0-L5 authority levels. Includes a `MOCK_CLERK_AUTH` mode for running locally without Clerk keys.
4. **Periodic Notion Polling**: Connector client that polls databases every 5 minutes looking for page updates based on last-edited timestamps.
5. **JSON Logging & Telemetry**: JSON-formatted logging via `structlog` and Prometheus metrics exporter under `/metrics`.
6. **Next.js 14 Admin Frontend**: Next.js App router dashboard containing an Admin Approval Inbox and a list-based Knowledge Explorer with sensitivity auditing.

---

## 🚀 Quickstart: Running Backend & Frontend

### 1. Run Backend Server
```bash
cd phase-2/backend
pip install -r requirements.txt
python run_backend.py
```
- API will start at `http://localhost:8000`.
- Prometheus metrics at `http://localhost:8000/metrics`.
- Swagger API docs at `http://localhost:8000/docs`.

### 2. Run Next.js Admin Panel
```bash
cd phase-2/frontend
npm install
npm run dev
```
- Open `http://localhost:3000` in your web browser.
- Uses mock authentication pass-through if no Clerk keys are loaded in environment.

---

## 🧪 Running Automated Test Suite
To run all 9 multi-tenant and integration tests cleanly:
```bash
python -m unittest discover -s phase-2/backend/tests
```
