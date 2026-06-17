import os

def load_env():
    """Helper to locate and read .env files up to 3 levels up."""
    env_paths = [
        os.path.join(os.path.dirname(__file__), "..", ".env"),
        os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
        os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env"),
        ".env"
    ]
    for path in env_paths:
        abs_path = os.path.abspath(path)
        if os.path.exists(abs_path):
            with open(abs_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if "=" in line:
                            k, v = line.split("=", 1)
                            os.environ[k.strip()] = v.strip().strip('"').strip("'").strip()
            break

# Load env variables on module import
load_env()

# LLM & Codex Settings
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "codex_cli")
AGENT_ENDPOINT = os.environ.get("AGENT_ENDPOINT", "ws://127.0.0.1:4500")
AGENT_MODEL = os.environ.get("AGENT_MODEL", "gpt-4o")

# Clerk Auth Configurations (Mocked/Disabled if blank or requested)
CLERK_PUBLIC_KEY = os.environ.get("CLERK_PUBLIC_KEY", "")
MOCK_CLERK_AUTH = os.environ.get("MOCK_CLERK_AUTH", "true").lower() == "true"

# Paths
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BACKEND_DIR, "data")
TENANTS_DIR = os.path.join(DATA_DIR, "tenants")

# Ensure base directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(TENANTS_DIR, exist_ok=True)
