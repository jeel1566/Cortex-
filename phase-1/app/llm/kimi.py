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

class KimiClient:
    def __init__(self, endpoint=None, api_key=None, model_name=None):
        provider = os.environ.get("LLM_PROVIDER", "azure").lower()
        if provider == "ollama":
            self.endpoint = endpoint or os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434/v1")
            self.api_key = api_key or "ollama"
            self.model_name = (model_name or os.environ.get("OLLAMA_MODEL", "llama3")).strip()
            # Auto start ollama and pull model
            ensure_ollama_running(self.model_name)
        else:
            self.endpoint = endpoint or os.environ.get("AZURE_ENDPOINT", "")
            self.api_key = api_key or os.environ.get("AZURE_API_KEY", "")
            self.model_name = model_name or os.environ.get("AZURE_MODEL_NAME", "kimi-k2.5")
            
    def chat_completion(self, messages: List[Dict[str, str]], temperature=0.7, max_tokens=2048, response_format=None) -> str:
        if not self.endpoint:
            raise ValueError("LLM endpoint must be set.")
            
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
            
        try:
            provider = os.environ.get("LLM_PROVIDER", "azure").lower()
            timeout_val = 300 if provider == "ollama" else 60
            response = requests.post(url, headers=headers, json=payload, timeout=timeout_val)
            response.raise_for_status()
            data = response.json()
            return data['choices'][0]['message']['content']
        except Exception as e:
            if 'response' in locals() and response is not None:
                print(f"API Error Response: {response.text}")
            raise RuntimeError(f"Kimi API request failed: {e}")

_client = None

def get_kimi_client() -> KimiClient:
    global _client
    if _client is None:
        _client = KimiClient()
    return _client

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
