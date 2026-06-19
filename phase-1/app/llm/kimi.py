import os
import requests
import json
import subprocess
import time
from typing import Any, Dict, List, Optional

def ensure_ollama_running(model_name="llama3"):
    model_name = model_name.strip()
    print("Checking if Ollama is running...")
    ollama_base_url = os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434/v1")
    # Parse base port/host (standard is http://localhost:11434)
    from urllib.parse import urlparse
    parsed = urlparse(ollama_base_url)
    ollama_host_url = f"{parsed.scheme}://{parsed.netloc}"
    
    try:
        response = requests.get(ollama_host_url)
        if response.status_code == 200 or "ollama" in response.text.lower():
            print("Ollama is already running.")
    except requests.exceptions.ConnectionError:
        print("Ollama is not running. Attempting to start it...")
        try:
            # Launch Ollama serve in the background
            if os.name == 'nt':  # Windows
                # We try to launch 'ollama serve'
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            else:  # Unix/macOS
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setpgrp)
            
            # Wait for Ollama to spin up
            for i in range(10):
                time.sleep(1)
                try:
                    res = requests.get(ollama_host_url)
                    if res.status_code == 200 or "ollama" in res.text.lower():
                        print("Ollama started successfully.")
                        break
                except requests.exceptions.ConnectionError:
                    continue
            else:
                raise RuntimeError("Failed to start Ollama. Please ensure Ollama is installed and run 'ollama serve' manually.")
        except FileNotFoundError:
            raise RuntimeError(
                "Ollama executable not found. Please ensure Ollama is installed and added to your system PATH.\n"
                "On macOS, you can download the Ollama app or install it via Homebrew: 'brew install ollama'."
            )
        except Exception as e:
            raise RuntimeError(f"Error starting Ollama: {e}")

    # Check if model is pulled
    print(f"Checking if model '{model_name}' is available...")
    try:
        # Check pulled models
        tags_response = requests.get(f"{ollama_host_url}/api/tags")
        if tags_response.status_code == 200:
            models = [m['name'] for m in tags_response.json().get('models', [])]
            model_tag = f"{model_name}:latest"
            if model_name in models or model_tag in models or any(m.startswith(model_name) for m in models):
                print(f"Model '{model_name}' is already pulled.")
                return
        
        # Pull the model
        print(f"Model '{model_name}' not found. Pulling model (this might take a few minutes)...")
        subprocess.run(["ollama", "pull", model_name], check=True)
        print(f"Model '{model_name}' pulled successfully.")
    except Exception as e:
        print(f"Warning during model check/pull: {e}. Attempting to proceed anyway.")

def load_env():
    # Search for .env in potential parent paths relative to this file
    env_paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"),
        os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.join(os.path.dirname(__file__), ".env"),
        ".env"
    ]
    for path in env_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            if "=" in line:
                                k, v = line.split("=", 1)
                                os.environ[k.strip()] = v.strip().strip('"').strip("'").strip()
                break
            except Exception as e:
                print(f"Warning: Failed to load .env from {abs_path}: {e}")

# Pre-load env variables
load_env()

try:
    from llama_index.core.llms import CustomLLM, CompletionResponse, CompletionResponseGen, LLMMetadata
    from llama_index.core.llms.callbacks import llm_completion_callback
    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    LLAMA_INDEX_AVAILABLE = False
    # Mock class for environment setup
    class CustomLLM:
        def __init__(self, **kwargs): pass

from urllib.parse import urlparse

# ──────────────────────────────────────────────────────────────────────────────
# CortexLLMClient — unified LLM client supporting three provider modes:
#   1. local_ai   → Ollama running locally (default: http://localhost:11434/v1)
#   2. web_api    → Any OpenAI-compatible web API (Groq, Azure, OpenAI, etc.)
#   3. coding_agent → Developer-facing AI agents (Codex, Copilot, Antigravity,
#                     etc.) via a local or remote OpenAI-compatible endpoint
#
# Select the mode via the LLM_PROVIDER environment variable.
# For backward compatibility, "ollama" maps to local_ai and "azure" maps to web_api.
# ──────────────────────────────────────────────────────────────────────────────
def ensure_codex_server_running(endpoint="ws://127.0.0.1:4500"):
    print(f"Checking if Codex App Server is running at {endpoint}...")
    from urllib.parse import urlparse
    import socket
    import subprocess
    import os
    import time
    
    parsed = urlparse(endpoint)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 4500
    
    # Try to connect to check if running
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    try:
        s.connect((host, port))
        s.close()
        print("Codex App Server is already running.")
        return
    except (ConnectionRefusedError, socket.timeout, OSError):
        print("Codex App Server is not running. Attempting to start it...")
        try:
            listen_arg = f"ws://{host}:{port}"
            if os.name == 'nt':  # Windows
                subprocess.Popen(
                    ["codex", "app-server", "--listen", listen_arg],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    shell=True
                )
            else:  # Unix/macOS
                subprocess.Popen(
                    ["codex", "app-server", "--listen", listen_arg],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setpgrp
                )
            
            # Wait for Codex App Server to spin up
            for i in range(15):
                time.sleep(1)
                s2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s2.settimeout(1.0)
                try:
                    s2.connect((host, port))
                    s2.close()
                    print("Codex App Server started successfully.")
                    break
                except (ConnectionRefusedError, socket.timeout, OSError):
                    continue
            else:
                raise RuntimeError(f"Failed to start Codex App Server. Please ensure Codex CLI is installed and run 'codex app-server --listen {listen_arg}' manually.")
        except FileNotFoundError:
            raise RuntimeError(
                "Codex executable not found. Please ensure Codex CLI is installed and added to your system PATH."
            )
        except Exception as e:
            raise RuntimeError(f"Error starting Codex App Server: {e}")

def run_async_in_thread(coro):
    import threading
    import asyncio
    from queue import Queue
    
    q = Queue()
    
    def worker():
        try:
            val = asyncio.run(coro)
            q.put((True, val))
        except Exception as e:
            q.put((False, e))
            
    t = threading.Thread(target=worker)
    t.start()
    t.join()
    
    success, res = q.get()
    if success:
        return res
    else:
        raise res

async def _execute_prompt_ws(endpoint, prompt, model_name=None):
    import websockets
    import json
    async with websockets.connect(endpoint) as ws:
        # 1. Initialize
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "method": "initialize",
            "id": 1,
            "params": {
                "clientInfo": {
                    "name": "cortex-client",
                    "version": "1.0.0"
                }
            }
        }))
        while True:
            resp_str = await ws.recv()
            if json.loads(resp_str).get("id") == 1:
                break
        
        # 2. Start Thread
        start_params = {
            "ephemeral": True,
            "approvalPolicy": "never",
            "sandbox": "read-only"
        }
        if model_name:
            start_params["model"] = model_name
            
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "method": "thread/start",
            "id": 2,
            "params": start_params
        }))
        
        thread_id = None
        while True:
            resp_str = await ws.recv()
            thread_data = json.loads(resp_str)
            if thread_data.get("id") == 2:
                thread_id = thread_data.get("result", {}).get("thread", {}).get("id")
                break
        if not thread_id:
            raise RuntimeError("Failed to obtain thread ID from Codex App Server.")
            
        # 3. Start Turn
        await ws.send(json.dumps({
            "jsonrpc": "2.0",
            "method": "turn/start",
            "id": 3,
            "params": {
                "threadId": thread_id,
                "input": [
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        }))
        
        # Read incoming messages until turn is complete
        response_text = None
        while True:
            resp = await ws.recv()
            data = json.loads(resp)
            method = data.get("method")
            if method == "item/completed":
                params = data.get("params", {})
                item = params.get("item", {})
                if item.get("type") == "agentMessage":
                    response_text = item.get("text")
            elif method == "thread/status/changed":
                status_type = data.get("params", {}).get("status", {}).get("type")
                if status_type == "idle":
                    break
                elif status_type == "systemError":
                    raise RuntimeError("Codex thread entered systemError status.")
            elif method == "error":
                error_msg = data.get("params", {}).get("error", {}).get("message", "Unknown Codex error")
                raise RuntimeError(f"Codex server error: {error_msg}")
        
        if response_text is None:
            raise RuntimeError("Codex App Server completed without producing an agentMessage.")
        return response_text

class CortexLLMClient:
    """
    Unified LLM client for the Cortex Knowledge OS.

    Provider modes (set via LLM_PROVIDER env var):
        local_ai     | Ollama running locally
        web_api      | Any OpenAI-compatible web API (Groq, Azure, OpenAI, etc.)
        coding_agent | Coding agent endpoints (Codex, GitHub Copilot,
                     | Antigravity, etc.)
        openai       | Standard OpenAI API
        deepseek     | Direct DeepSeek API
        anthropic    | Direct Anthropic API
        azure        | Direct Azure OpenAI API

    Backward-compatible aliases: "ollama" → local_ai, "azure" → web_api (if legacy).
    """

    # Map legacy and canonical provider names → canonical key
    _PROVIDER_MAP = {
        "ollama":        "local_ai",
        "local_ai":      "local_ai",
        "local":         "local_ai",
        "azure":         "azure",
        "web_api":       "web_api",
        "web":           "web_api",
        "openai":        "openai",
        "deepseek":      "deepseek",
        "anthropic":     "anthropic",
        "groq":          "web_api",
        "coding_agent":  "coding_agent",
        "codex":         "codex_cli",
        "codex_cli":     "codex_cli",
        "copilot":       "coding_agent",
        "antigravity":   "coding_agent",
        "agent":         "coding_agent",
    }

    def __init__(self, endpoint=None, api_key=None, model_name=None, provider=None, model=None):
        raw_provider = (provider or os.environ.get("LLM_PROVIDER", "web_api")).lower().strip()
        self.provider = self._PROVIDER_MAP.get(raw_provider, "web_api")
        model_val = model_name or model

        if self.provider == "local_ai":
            self.endpoint   = endpoint   or os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434/v1")
            self.api_key    = api_key    or "ollama"
            self.model_name = (model_val or os.environ.get("OLLAMA_MODEL", "llama3")).strip()
            ensure_ollama_running(self.model_name)

        elif self.provider == "coding_agent":
            # Coding agents expose an OpenAI-compatible endpoint locally or remotely.
            # Point AGENT_ENDPOINT to whatever port the agent listens on.
            self.endpoint   = endpoint   or os.environ.get("AGENT_ENDPOINT", "http://localhost:11435/v1")
            self.api_key    = api_key    or os.environ.get("AGENT_API_KEY", "agent")
            self.model_name = model_val or os.environ.get("AGENT_MODEL", "gpt-4o")
            print(f"[CortexLLM] Using Coding Agent provider -> {self.model_name} @ {self.endpoint}")

        elif self.provider == "codex_cli":
            self.endpoint   = endpoint   or os.environ.get("AGENT_ENDPOINT", "ws://127.0.0.1:4500")
            self.api_key    = api_key    or os.environ.get("AGENT_API_KEY", "cli")
            self.model_name = model_val or os.environ.get("AGENT_MODEL") or os.environ.get("CODEX_MODEL") or ""
            ensure_codex_server_running(self.endpoint)
            print(f"[CortexLLM] Using Codex CLI provider -> {self.model_name or 'default'} @ {self.endpoint}")

        elif self.provider == "openai":
            self.endpoint   = endpoint   or os.environ.get("LLM_ENDPOINT", "https://api.openai.com/v1")
            self.api_key    = api_key    or os.environ.get("LLM_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "")
            self.model_name = model_val or os.environ.get("LLM_MODEL", "gpt-4o")

        elif self.provider == "deepseek":
            self.endpoint   = endpoint   or os.environ.get("LLM_ENDPOINT", "https://api.deepseek.com/v1")
            self.api_key    = api_key    or os.environ.get("LLM_API_KEY", "") or os.environ.get("DEEPSEEK_API_KEY", "")
            self.model_name = model_val or os.environ.get("LLM_MODEL", "deepseek-chat")

        elif self.provider == "anthropic":
            self.endpoint   = endpoint   or os.environ.get("LLM_ENDPOINT", "https://api.anthropic.com/v1/messages")
            self.api_key    = api_key    or os.environ.get("LLM_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
            self.model_name = model_val or os.environ.get("LLM_MODEL", "claude-3-5-sonnet-20240620")

        elif self.provider == "azure":
            self.endpoint   = endpoint   or os.environ.get("AZURE_ENDPOINT", "") or os.environ.get("LLM_ENDPOINT", "")
            self.api_key    = api_key    or os.environ.get("AZURE_API_KEY", "") or os.environ.get("LLM_API_KEY", "")
            self.model_name = model_val or os.environ.get("AZURE_MODEL_NAME", "kimi-k2.5")

        else:  # web_api
            self.endpoint   = endpoint   or os.environ.get("AZURE_ENDPOINT",      "") \
                                         or os.environ.get("WEB_API_ENDPOINT",    "") \
                                         or os.environ.get("LLM_ENDPOINT",         "")
            self.api_key    = api_key    or os.environ.get("AZURE_API_KEY",        "") \
                                         or os.environ.get("WEB_API_KEY",         "") \
                                         or os.environ.get("LLM_API_KEY",          "")
            self.model_name = model_name or os.environ.get("AZURE_MODEL_NAME",    "") \
                                         or os.environ.get("WEB_API_MODEL",       "llama-3.1-8b-instant")
            
    def chat_completion(self, messages: List[Dict[str, str]], temperature=0.7, max_tokens=2048, response_format=None) -> str:
        # Dynamic hybrid model routing for Groq endpoint
        current_model = self.model_name
        if self.provider == "web_api" and self.endpoint and "groq.com" in self.endpoint.lower():
            total_chars = sum(len(m.get("content", "")) for m in messages)
            estimated_tokens = total_chars // 4
            if estimated_tokens > 4500:
                current_model = "meta-llama/llama-4-scout-17b-16e-instruct"
            else:
                current_model = "llama-3.1-8b-instant"
                
        if self.provider == "codex_cli":
            # Convert messages to a formatted prompt string
            prompt_parts = []
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "system":
                    prompt_parts.append(f"System instructions:\n{content}\n")
                elif role == "user":
                    prompt_parts.append(f"User request:\n{content}\n")
                elif role == "assistant":
                    prompt_parts.append(f"Assistant response:\n{content}\n")
                else:
                    prompt_parts.append(f"{role.capitalize()}:\n{content}\n")
            
            prompt = "\n".join(prompt_parts)
            
            # Execute prompt via the running Codex App Server using the WebSocket client in a thread
            print(f"[CortexLLM] Sending prompt to Codex App Server at {self.endpoint}")
            coro = _execute_prompt_ws(self.endpoint, prompt, self.model_name)
            return run_async_in_thread(coro)

        if not self.endpoint:
            raise ValueError("LLM endpoint must be set.")

        from urllib.parse import urlparse
            
        if self.provider == "anthropic":
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            # Translate messages for Anthropic (extract system prompt, map roles)
            system_prompt = None
            anthropic_messages = []
            for msg in messages:
                role = msg.get("role")
                content = msg.get("content")
                if role == "system":
                    system_prompt = content
                else:
                    role_mapped = "user" if role == "user" else "assistant"
                    anthropic_messages.append({"role": role_mapped, "content": content})
                    
            payload = {
                "model": current_model,
                "messages": anthropic_messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            if system_prompt:
                payload["system"] = system_prompt
                
            url = self.endpoint
        else:
            # Parse endpoint to cleanly build the chat completions URL (handling query params)
            parsed = urlparse(self.endpoint)
            path = parsed.path
            if path.endswith("/chat/completions"):
                path = path[:-17]
            path = path.rstrip("/") + "/chat/completions"
            
            scheme = parsed.scheme or "https"
            netloc = parsed.netloc
            url = f"{scheme}://{netloc}{path}"
            if parsed.query:
                url += f"?{parsed.query}"
            print(f"[DEBUG] self.endpoint: '{self.endpoint}'")
            print(f"[DEBUG] constructed url: '{url}'")

            headers = {
                "Content-Type": "application/json"
            }
            if self.provider == "azure":
                headers["api-key"] = self.api_key
                headers["Authorization"] = f"Bearer {self.api_key}"
            else:
                headers["Authorization"] = f"Bearer {self.api_key}"
            
            payload = {
                "model": current_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            if response_format:
                payload["response_format"] = response_format
            
        print(f"[CortexLLM] provider={self.provider} model={current_model}")
        max_retries = 5
        base_delay = 2.0
        response = None
        
        for attempt in range(max_retries):
            try:
                timeout_val = 300 if self.provider == "local_ai" else 60
                response = requests.post(url, headers=headers, json=payload, timeout=timeout_val)
                
                # Check for 429 rate limit
                if response.status_code == 429:
                    retry_after = response.headers.get("retry-after")
                    wait_time = base_delay * (2 ** attempt)
                    if retry_after:
                        try:
                            wait_time = float(retry_after)
                        except ValueError:
                            pass
                    else:
                        try:
                            err_json = response.json()
                            err_msg = err_json.get("error", {}).get("message", "")
                            print(f"[RATE_LIMIT] 429 Rate limit hit: {err_msg}")
                            # Match e.g. "try again in 1m23.4s" or "try again in 23s"
                            import re
                            m = re.search(r'try again in (?:(\d+)m)?([\d.]+)s', err_msg)
                            if m:
                                mins = float(m.group(1)) if m.group(1) else 0.0
                                secs = float(m.group(2))
                                wait_time = mins * 60 + secs + 0.5
                        except Exception:
                            pass
                    
                    print(f"[RATE_LIMIT] Request rate limited. Waiting {wait_time:.2f} seconds before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                data = response.json()
                if self.provider == "anthropic":
                    return data['content'][0]['text']
                else:
                    return data['choices'][0]['message']['content']
            except requests.exceptions.HTTPError as he:
                if response is not None and response.status_code == 429:
                    pass
                else:
                    if response is not None:
                        print(f"API Error Response: {response.text}")
                    if attempt == max_retries - 1:
                        raise
            except Exception as e:
                if attempt == max_retries - 1:
                    if response is not None:
                        print(f"API Error Response: {response.text}")
                    raise RuntimeError(f"Kimi API request failed: {e}")
                wait_time = base_delay * (2 ** attempt)
                print(f"[WARNING] API request failed with error: {e}. Retrying in {wait_time:.2f}s...")
                time.sleep(wait_time)
        
        # If the loop finishes without returning, it means all attempts failed (usually with 429 status)
        if response is not None and response.status_code == 429:
            raise RuntimeError(f"Kimi API request failed with 429 Rate Limit after {max_retries} attempts.")
        raise RuntimeError(f"Kimi API request failed after {max_retries} attempts.")

# ── Backward-compat alias ──────────────────────────────────────────────────────
# KimiClient is kept as an alias so existing code continues to work unchanged.
KimiClient = CortexLLMClient

_client = None

def get_kimi_client() -> CortexLLMClient:
    """Returns the global singleton CortexLLMClient (a.k.a. KimiClient)."""
    global _client
    if _client is None:
        _client = CortexLLMClient()
    return _client

# Convenience alias
get_cortex_client = get_kimi_client

if LLAMA_INDEX_AVAILABLE:
    class KimiLlamaIndexLLM(CustomLLM):
        model_name: str = "kimi-k2.5"
        
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            # Pre-warm client
            get_kimi_client()
            
        @property
        def metadata(self) -> LLMMetadata:
            return LLMMetadata(
                context_window=32768,
                num_output=4096,
                model_name=self.model_name
            )
            
        @llm_completion_callback()
        def complete(self, prompt: str, **kwargs: Any) -> CompletionResponse:
            client = get_kimi_client()
            messages = [{"role": "user", "content": prompt}]
            response_text = client.chat_completion(messages, temperature=0.1)
            return CompletionResponse(text=response_text)
            
        @llm_completion_callback()
        def stream_complete(self, prompt: str, **kwargs: Any) -> CompletionResponseGen:
            raise NotImplementedError("Streaming not supported for Kimi custom LLM.")
else:
    class KimiLlamaIndexLLM(CustomLLM):
        def __init__(self, **kwargs):
            raise ImportError("llama-index-core is not installed.")
