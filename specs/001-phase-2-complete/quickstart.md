# Quickstart: Phase 2 — Make it Complete

Follow these steps to run and test the Phase 2 backend service and frontend application locally.

---

## 💻 Backend Setup

1. **Navigate to the Backend directory**:
   ```bash
   cd phase-2/backend
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**:
   Create a `.env` file in `phase-2/backend/` containing:
   ```env
   LLM_PROVIDER=codex_cli
   AGENT_ENDPOINT=ws://127.0.0.1:4500
   CLERK_PUBLIC_KEY=your_clerk_pubkey
   ```

4. **Launch the FastAPI Server**:
   ```bash
   python run_backend.py
   ```
   The backend will start at `http://localhost:8000`.

5. **Run Tests**:
   ```bash
   pytest tests/
   ```

---

## 🖥️ Frontend Setup

1. **Navigate to the Frontend directory**:
   ```bash
   cd phase-2/frontend
   ```

2. **Install Node dependencies**:
   ```bash
   npm install
   ```

3. **Configure Clerk Auth**:
   Create a `.env.local` file in `phase-2/frontend/` containing:
   ```env
   NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=your_clerk_pubkey
   CLERK_SECRET_KEY=your_clerk_secret
   ```

4. **Start the Next.js Dev Server**:
   ```bash
   npm run dev
   ```
   Open `http://localhost:3000` in your web browser.
