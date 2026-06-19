### How to Check the Feature

#### 1. Run the Automated Test Suite
Run the new unit tests to verify that Ollama, Anthropic, Custom Web URL, and Azure OpenAI endpoint formatting works correctly:
```bash
python -m unittest phase-1/tests/test_llm.py
```

#### 2. Configure the Environment
Open [.env](file:///Users/aniketsatpathy/Desktop/Aniket/Cortex/.env) and configure the provider of your choice.

**Example 1: Using a Custom Web URL (e.g. OpenRouter or together.ai)**
```bash
LLM_PROVIDER="web_url"
LLM_ENDPOINT="https://api.openrouter.ai/api/v1"
LLM_API_KEY="your-openrouter-key"
LLM_MODEL="meta-llama/llama-3-8b-instruct"
```

**Example 2: Using Local LLM (Ollama)**
```bash
LLM_PROVIDER="ollama"
LLM_ENDPOINT="http://127.0.0.1:11434/v1"
LLM_MODEL="qwen3:14b"
```

**Example 3: Direct Anthropic Cloud API**
```bash
LLM_PROVIDER="anthropic"
LLM_API_KEY="your-claude-key"
LLM_MODEL="claude-3-5-sonnet-20240620"
```

#### 3. Test via Python Interactively
You can test the client dynamically in Python by importing `get_kimi_client` (or `get_cortex_client`) from `app.llm.kimi`:

```python
from app.llm.kimi import get_kimi_client

# Initializes based on your active .env settings
client = get_kimi_client()

response = client.chat_completion(
    messages=[{"role": "user", "content": "Write a short poem about coding."}],
    temperature=0.7
)
print(response)
```