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
            if os.name == 'nt':
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            else:
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, preexec_fn=os.setpgrp)
            
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
                "Ollama executable not found. Please ensure Ollama is installed and added to your system PATH."
            )
        except Exception as e:
            raise RuntimeError(f"Error starting Ollama: {e}")

    print(f"Checking if model '{model_name}' is available...")
    try:
        tags_response = requests.get(f"{ollama_host_url}/api/tags")
        if tags_response.status_code == 200:
            models = [m['name'] for m in tags_response.json().get('models', [])]
            model_tag = f"{model_name}:latest"
            if model_name in models or model_tag in models or any(m.startswith(model_name) for m in models):
                print(f"Model '{model_name}' is already pulled.")
                return
        
        print(f"Model '{model_name}' not found. Pulling model (this might take a few minutes)...")
        subprocess.run(["ollama", "pull", model_name], check=True)
        print(f"Model '{model_name}' pulled successfully.")
    except Exception as e:
        print(f"Warning during model check/pull: {e}. Attempting to proceed anyway.")

def ensure_codex_server_running(endpoint="ws://127.0.0.1:4500"):
    print(f"Checking if Codex App Server is running at {endpoint}...")
    from urllib.parse import urlparse
    import socket
    
    parsed = urlparse(endpoint)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 4500
    
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
            if os.name == 'nt':
                subprocess.Popen(
                    ["codex", "app-server", "--listen", listen_arg],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                    shell=True
                )
            else:
                subprocess.Popen(
                    ["codex", "app-server", "--listen", listen_arg],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setpgrp
                )
            
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
        await ws.recv()
        
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
        thread_data = json.loads(await ws.recv())
        thread_id = thread_data.get("result", {}).get("thread", {}).get("id")
        if not thread_id:
            raise RuntimeError("Failed to obtain thread ID from Codex App Server.")
            
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
        
        if response_text is None:
            raise RuntimeError("Codex App Server completed without producing an agentMessage.")
        return response_text

class CortexLLMClient:
    _PROVIDER_MAP = {
        "ollama":        "local_ai",
        "local_ai":      "local_ai",
        "local":         "local_ai",
        "azure":         "web_api",
        "web_api":       "web_api",
        "web":           "web_api",
        "openai":        "web_api",
        "groq":          "web_api",
        "coding_agent":  "coding_agent",
        "codex":         "codex_cli",
        "codex_cli":     "codex_cli",
        "copilot":       "coding_agent",
        "antigravity":   "coding_agent",
        "agent":         "coding_agent",
    }

    def __init__(self, endpoint=None, api_key=None, model_name=None):
        raw_provider = os.environ.get("LLM_PROVIDER", "web_api").lower().strip()
        self.provider = self._PROVIDER_MAP.get(raw_provider, "web_api")

        if self.provider == "local_ai":
            self.endpoint   = endpoint   or os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434/v1")
            self.api_key    = api_key    or "ollama"
            self.model_name = (model_name or os.environ.get("OLLAMA_MODEL", "llama3")).strip()
            ensure_ollama_running(self.model_name)

        elif self.provider == "coding_agent":
            self.endpoint   = endpoint   or os.environ.get("AGENT_ENDPOINT", "http://localhost:11435/v1")
            self.api_key    = api_key    or os.environ.get("AGENT_API_KEY", "agent")
            self.model_name = model_name or os.environ.get("AGENT_MODEL", "gpt-4o")

        elif self.provider == "codex_cli":
            self.endpoint   = endpoint   or os.environ.get("AGENT_ENDPOINT", "ws://127.0.0.1:4500")
            self.api_key    = api_key    or os.environ.get("AGENT_API_KEY", "cli")
            self.model_name = model_name or os.environ.get("AGENT_MODEL") or os.environ.get("CODEX_MODEL") or ""
            ensure_codex_server_running(self.endpoint)

        else:
            self.endpoint   = endpoint   or os.environ.get("AZURE_ENDPOINT",      "") \
                                         or os.environ.get("WEB_API_ENDPOINT",    "")
            self.api_key    = api_key    or os.environ.get("AZURE_API_KEY",        "") \
                                         or os.environ.get("WEB_API_KEY",         "")
            self.model_name = model_name or os.environ.get("AZURE_MODEL_NAME",    "") \
                                         or os.environ.get("WEB_API_MODEL",       "llama-3.1-8b-instant")
            
    def chat_completion(self, messages: List[Dict[str, str]], temperature=0.7, max_tokens=2048, response_format=None) -> str:
        if self.provider == "codex_cli":
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
            coro = _execute_prompt_ws(self.endpoint, prompt, self.model_name)
            return run_async_in_thread(coro)

        if not self.endpoint:
            raise ValueError("LLM endpoint must be set.")
            
        from urllib.parse import urlparse
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
            
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        if response_format:
            payload["response_format"] = response_format
            
        max_retries = 5
        base_delay = 2.0
        response = None
        
        for attempt in range(max_retries):
            try:
                provider = os.environ.get("LLM_PROVIDER", "azure").lower()
                timeout_val = 300 if provider == "ollama" else 60
                response = requests.post(url, headers=headers, json=payload, timeout=timeout_val)
                
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
                            import re
                            m = re.search(r'try again in (?:(\d+)m)?([\d.]+)s', err_msg)
                            if m:
                                mins = float(m.group(1)) if m.group(1) else 0.0
                                secs = float(m.group(2))
                                wait_time = mins * 60 + secs + 0.5
                        except Exception:
                            pass
                    
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                data = response.json()
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
                    raise RuntimeError(f"Kimi API request failed: {e}")
                wait_time = base_delay * (2 ** attempt)
                time.sleep(wait_time)

_client = None

def get_kimi_client() -> CortexLLMClient:
    global _client
    if _client is None:
        _client = CortexLLMClient()
    return _client
