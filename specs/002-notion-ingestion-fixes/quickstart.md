# Quickstart: Notion Ingestion & Page Validation Fixes

Follow these steps to run and test the Notion Ingestion Crawler fixes and Strict Pre-save Page Validation.

---

## 🧪 Testing the Crawler and Validator

1. **Navigate to the Backend directory**:
   ```bash
   cd phase-2/backend
   ```

2. **Verify Python Virtual Environment is Active**:
   Ensure dependencies are installed:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run Ingestion and Crawler Tests**:
   Verify that recursive block retrieval from Notion is mocked correctly and builds full documents:
   ```bash
   pytest tests/test_notion_crawler.py -v
   ```

4. **Run Strict Validator Tests**:
   Verify that the validator correctly rejects prompt leak strings (like `</output_format>`) and missing YAML frontmatter, and assets are not committed:
   ```bash
   pytest tests/test_strict_validator.py -v
   ```

---

## 🖥️ Verifying in UI (Notion Access Check)

1. **Navigate to the Frontend directory**:
   ```bash
   cd phase-2/frontend
   ```

2. **Run Dev Server**:
   ```bash
   npm run dev
   ```

3. **Check Connection Status**:
   Navigate to the Settings tab in the Knowledge Dashboard (`/settings/notion`). Ensure the screen displays:
   - Total pages/databases found
   - Skipped blank pages
   - Ingestion status logs showing loud errors instead of fallback demo text on failures.
