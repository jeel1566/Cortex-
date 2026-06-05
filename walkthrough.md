# Walkthrough of Ollama RAG Support & Portable Dataset

We have successfully completed all planned tasks to ensure that the project is completely self-contained and configured for running the RAG benchmark locally using **Ollama**.

## What was Changed

1. **Packaged Dataset**:
   - Created the [data](file:///d:/Cortex/phase-1/data) directory within the workspace.
   - Copied the dataset files `messages.csv` and `users.csv` into it.
   - Updated [local_rag.py](file:///d:/Cortex/phase-1/app/baseline/local_rag.py#L476-L486) so the RAG baseline uses relative paths to this workspace data folder. This ensures the benchmark works out-of-the-box when the codebase is shared with others.

2. **Ollama Integration & Auto-Start**:
   - Added the [ensure_ollama_running](file:///d:/Cortex/phase-1/app/llm/kimi.py#L7-L59) function to check if the Ollama server is running (checking local port `11434` on `127.0.0.1` to bypass Windows IPv6 resolution issues).
   - If not running, the script automatically spawns `ollama serve` in the background and waits for it to become responsive.
   - Checks if the specified model is pulled, and calls `ollama pull` synchronously if it is missing.
   - Updated the Kimi API request timeout from `60` to `300` seconds when using Ollama to accommodate the initial model pre-loading time on CPU/memory-constrained environments.

3. **Ollama Configuration Settings**:
   - Added configuration switches to [.env](file:///d:/Cortex/phase-1/.env):
     ```bash
     LLM_PROVIDER="ollama"
     OLLAMA_ENDPOINT="http://127.0.0.1:11434/v1"
     OLLAMA_MODEL="llama3"
     ```
   - Default provider is set to `"ollama"` with model `"llama3"`.

## Verification Results

1. **Unit Tests**:
   - Ran `python tests/test_phase1.py` successfully. All component unit tests passed.

2. **Integration & Auto-Start Test**:
   - Configured the provider to `"ollama"` and model to `"gemma:2b"` (which was already pulled on the local machine).
   - Ran a test script that verified:
     - Ollama server started up automatically.
     - Connection established via the OpenAI-compatible `/v1` endpoint.
     - Prompt successfully generated a response from the model.

---

## Instructions for Your Friend to Run the Benchmark

1. Make sure **Ollama** is installed on the system.
2. In the `d:\Cortex\phase-1` directory, open the `.env` file and make sure:
   - `LLM_PROVIDER="ollama"`
   - `OLLAMA_MODEL="<desired_model_name>"` (e.g. `llama3` or `qwen2.5`)
3. Open a terminal, go to `phase-1`, and run:
   ```bash
   python app/baseline/local_rag.py
   ```
4. The system will:
   - Start the Ollama server in the background (if it isn't running).
   - Pull the specified model (if it isn't downloaded yet).
   - Read the dataset files directly from the local `data/` folder.
   - Query the questions in `eval/ground_truth.json` and save results to `eval/rag_baseline.json`.
