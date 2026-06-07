# Walkthrough of Ollama RAG Support & Portable Dataset

We have successfully completed all planned tasks to ensure that the project is completely self-contained and configured for running the RAG benchmark locally using **Ollama**.

## What was Changed

1. **Packaged Dataset**:
   - Created the [data](file:///D:/Cortex/phase-1/data) directory within the workspace.
   - Copied the dataset files `messages.csv` and `users.csv` into it.
   - Updated [local_rag.py](file:///D:/Cortex/phase-1/app/baseline/local_rag.py#L476-L486) so the RAG baseline uses relative paths to this workspace data folder. This ensures the benchmark works out-of-the-box when the codebase is shared with others.

2. **Ollama Integration & Auto-Start**:
   - Added the [ensure_ollama_running](file:///D:/Cortex/phase-1/app/llm/kimi.py#L7-L59) function to check if the Ollama server is running (checking local port `11434` on `127.0.0.1` to bypass Windows IPv6 resolution issues).
   - If not running, the script automatically spawns `ollama serve` in the background and waits for it to become responsive.
   - Checks if the specified model is pulled, and calls `ollama pull` synchronously if it is missing.
   - Updated the Kimi API request timeout from `60` to `300` seconds when using Ollama to accommodate the initial model pre-loading time on CPU/memory-constrained environments.

3. **Ollama Configuration Settings**:
   - Added configuration switches to [.env](file:///D:/Cortex/phase-1/.env):
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

## Walkthrough: Downloading & Running on macOS

Follow these steps to clone the codebase, install all dependencies, and run the RAG baseline on a macOS environment.

### Step 1: Download / Clone the Repository
Open a terminal on your Mac and clone the repository using Git:
```bash
git clone git@github.com:jeel1566/Cortex-.git
cd Cortex-/phase-1
```

### Step 2: Install Ollama
You need **Ollama** installed on your Mac to run the LLM locally. You can install it in one of two ways:
* **Option A (Homebrew - Recommended)**:
  If you have Homebrew installed, run:
  ```bash
  brew install ollama
  ```
* **Option B (Direct Download)**:
  Download the Ollama macOS application from [ollama.com/download](https://ollama.com/download) and drag it to your Applications folder.

### Step 3: Set Up Python (3.8+)
macOS often comes with an older version of Python or no default `python3` command.
1. Check if Python is installed:
   ```bash
   python3 --version
   ```
2. If Python is not installed or is older than 3.8, install it via Homebrew:
   ```bash
   brew install python
   ```

### Step 4: Create a Virtual Environment & Install Dependencies
It is highly recommended to use a virtual environment to manage dependencies.
1. In the `Cortex-/phase-1` directory, create a virtual environment:
   ```bash
   python3 -m venv venv
   ```
2. Activate the virtual environment:
   ```bash
   source venv/bin/activate
   ```
3. Install all python packages from [requirements.txt](file:///D:/Cortex/phase-1/requirements.txt):
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

### Step 5: Configure the Environment
Ensure your [.env](file:///D:/Cortex/phase-1/.env) file is configured to use Ollama:
```bash
LLM_PROVIDER="ollama"
OLLAMA_ENDPOINT="http://127.0.0.1:11434/v1"
OLLAMA_MODEL="llama3"
```
*(If you want to run a smaller model on M-series Mac CPUs/GPUs, you can set `OLLAMA_MODEL="gemma:2b"` or `OLLAMA_MODEL="qwen2.5:0.5b"`)*

### Step 6: Run the Benchmark
Execute the RAG baseline pipeline:
```bash
python app/baseline/local_rag.py
```

#### What happens under the hood when you run this?
1. The script checks if Ollama is running. If not, it starts it in the background (`ollama serve`).
2. It checks if the model (`llama3`) is pulled locally. If not, it automatically downloads it (`ollama pull llama3`).
3. It loads the dataset (`messages.csv` and `users.csv`) using relative paths from the local `data/` folder.
4. It initializes the local `NumPyVectorIndex` and queries the benchmark questions, outputting results to `eval/rag_baseline.json`.
