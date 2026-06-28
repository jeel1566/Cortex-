"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import { SyncProvider } from "./SyncContext";

export default function MainAppWrapper({ children }: { children: React.ReactNode }) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [provider, setProvider] = useState<string>("not_configured");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form states
  const [selectedProvider, setSelectedProvider] = useState<"ollama" | "web_api" | "codex">("web_api");
  const [ollamaEndpoint, setOllamaEndpoint] = useState("http://localhost:11434/v1");
  const [ollamaModel, setOllamaModel] = useState("llama3");
  const [webApiEndpoint, setWebApiEndpoint] = useState("");
  const [webApiKey, setWebApiKey] = useState("");
  const [webApiModel, setWebApiModel] = useState("llama-3.1-8b-instant");
  const [codexEndpoint, setCodexEndpoint] = useState("ws://127.0.0.1:4500");
  const [codexModel, setCodexModel] = useState("");

  const getAuthToken = async () => {
    if (process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) {
      try {
        const token = await getToken();
        if (token) return token;
      } catch (e) {
        console.warn("Clerk token acquisition failed, using fallback.", e);
      }
    }
    // Fallback base64 mock token (represents tenant_a L5 Admin)
    const mockPayload = { tenant_id: "tenant_a", authority_level: 5, name: "Admin (Mock Tenant)" };
    return btoa(JSON.stringify(mockPayload));
  };

  const fetchSettings = async () => {
    setLoading(true);
    try {
      const token = await getAuthToken();
      const res = await fetch("http://127.0.0.1:8000/v1/settings", {
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });
      if (res.ok) {
        const data = await res.json();
        setProvider(data.ai_provider);
        if (data.ai_provider !== "not_configured") {
          setSelectedProvider(data.ai_provider);
        }
        if (data.config) {
          const cfg = data.config;
          if (cfg.ollama_endpoint) setOllamaEndpoint(cfg.ollama_endpoint);
          if (cfg.ollama_model) setOllamaModel(cfg.ollama_model);
          if (cfg.web_api_endpoint) setWebApiEndpoint(cfg.web_api_endpoint);
          if (cfg.web_api_key) setWebApiKey(cfg.web_api_key);
          if (cfg.web_api_model) setWebApiModel(cfg.web_api_model);
          if (cfg.codex_endpoint) setCodexEndpoint(cfg.codex_endpoint);
          if (cfg.codex_model) setCodexModel(cfg.codex_model);
        }
      }
    } catch (e: any) {
      console.error("Failed to load settings:", e);
      setError("Unable to connect to Cortex Backend. Please make sure the backend server is running.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, [isLoaded, isSignedIn]);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    const config: any = {};
    if (selectedProvider === "ollama") {
      config.ollama_endpoint = ollamaEndpoint;
      config.ollama_model = ollamaModel;
    } else if (selectedProvider === "web_api") {
      config.web_api_endpoint = webApiEndpoint;
      config.web_api_key = webApiKey;
      config.web_api_model = webApiModel;
    } else if (selectedProvider === "codex") {
      config.codex_endpoint = codexEndpoint;
      config.codex_model = codexModel;
    }

    try {
      const token = await getAuthToken();
      const res = await fetch("http://127.0.0.1:8000/v1/settings", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          ai_provider: selectedProvider,
          config: config
        })
      });

      if (res.ok) {
        setProvider(selectedProvider);
      } else {
        const errData = await res.json();
        setError(errData.detail || "Failed to save settings. Please verify backend connection.");
      }
    } catch (err: any) {
      setError(err.message || "Failed to send settings update.");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: "flex", flex: 1, height: "80vh", justifyContent: "center", alignItems: "center", color: "var(--text-secondary)" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ width: "40px", height: "40px", border: "3px solid var(--border)", borderTopColor: "var(--accent)", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 1.5rem" }}></div>
          <div style={{ fontSize: "1.1rem", fontWeight: 500 }}>Initializing connection...</div>
          <style dangerouslySetInnerHTML={{ __html: `@keyframes spin { to { transform: rotate(360deg); } }` }} />
        </div>
      </div>
    );
  }

  if (provider === "not_configured") {
    return (
      <div style={{ maxWidth: "800px", margin: "2rem auto", padding: "1rem" }}>
        <div className="card" style={{ padding: "3rem 2.5rem", borderRadius: "16px" }}>
          <h2 style={{ fontSize: "2rem", marginBottom: "0.5rem", background: "linear-gradient(135deg, #fff 0%, #a1a1aa 100%)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
            Configure Cortex LLM Provider
          </h2>
          <p style={{ color: "var(--text-secondary)", marginBottom: "2.5rem", fontSize: "1rem", lineHeight: "1.5" }}>
            Cortex requires an AI Large Language Model (LLM) provider to classify, synthesize, and validate corporate knowledge pages. Please choose a provider option below to initialize the system.
          </p>

          {error && (
            <div style={{ background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.2)", color: "var(--error)", padding: "1rem", borderRadius: "8px", marginBottom: "2rem", fontSize: "0.9rem" }}>
              {error}
            </div>
          )}

          <form onSubmit={handleSave}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem", marginBottom: "2.5rem" }}>
              {/* Web API Choice */}
              <div 
                onClick={() => setSelectedProvider("web_api")}
                style={{ 
                  cursor: "pointer", 
                  padding: "1.5rem", 
                  borderRadius: "12px", 
                  background: selectedProvider === "web_api" ? "rgba(99, 102, 241, 0.08)" : "var(--bg-tertiary)", 
                  border: selectedProvider === "web_api" ? "2px solid var(--accent)" : "1px solid var(--border)",
                  transition: "all 0.2s ease",
                  textAlign: "center"
                }}
              >
                <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>🌐</div>
                <div style={{ fontWeight: 600, color: "#fff", marginBottom: "0.25rem" }}>Web API</div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Azure OpenAI, OpenAI, or Groq Cloud</div>
              </div>

              {/* Ollama Choice */}
              <div 
                onClick={() => setSelectedProvider("ollama")}
                style={{ 
                  cursor: "pointer", 
                  padding: "1.5rem", 
                  borderRadius: "12px", 
                  background: selectedProvider === "ollama" ? "rgba(99, 102, 241, 0.08)" : "var(--bg-tertiary)", 
                  border: selectedProvider === "ollama" ? "2px solid var(--accent)" : "1px solid var(--border)",
                  transition: "all 0.2s ease",
                  textAlign: "center"
                }}
              >
                <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>🦙</div>
                <div style={{ fontWeight: 600, color: "#fff", marginBottom: "0.25rem" }}>Ollama (Local)</div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Run models completely locally on your system</div>
              </div>

              {/* Codex Choice */}
              <div 
                onClick={() => setSelectedProvider("codex")}
                style={{ 
                  cursor: "pointer", 
                  padding: "1.5rem", 
                  borderRadius: "12px", 
                  background: selectedProvider === "codex" ? "rgba(99, 102, 241, 0.08)" : "var(--bg-tertiary)", 
                  border: selectedProvider === "codex" ? "2px solid var(--accent)" : "1px solid var(--border)",
                  transition: "all 0.2s ease",
                  textAlign: "center"
                }}
              >
                <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>💻</div>
                <div style={{ fontWeight: 600, color: "#fff", marginBottom: "0.25rem" }}>Codex CLI</div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Codex App-Server WebSocket connection</div>
              </div>
            </div>

            {/* Provider Forms */}
            <div style={{ background: "var(--bg-tertiary)", padding: "2rem", borderRadius: "12px", border: "1px solid var(--border)", marginBottom: "2rem" }}>
              {selectedProvider === "web_api" && (
                <div>
                  <h3 style={{ marginBottom: "1.5rem", color: "#fff", fontSize: "1.1rem" }}>Web API Settings</h3>
                  <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>API Endpoint URL</label>
                      <input 
                        type="text" 
                        required
                        value={webApiEndpoint} 
                        onChange={(e) => setWebApiEndpoint(e.target.value)} 
                        placeholder="https://api.groq.com/openai/v1"
                        style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "#fff" }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>API Key</label>
                      <input 
                        type="password" 
                        required
                        value={webApiKey} 
                        onChange={(e) => setWebApiKey(e.target.value)} 
                        placeholder="••••••••••••••••••••"
                        style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "#fff" }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Model Name</label>
                      <input 
                        type="text" 
                        required
                        value={webApiModel} 
                        onChange={(e) => setWebApiModel(e.target.value)} 
                        placeholder="llama-3.1-8b-instant"
                        style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "#fff" }}
                      />
                    </div>
                  </div>
                </div>
              )}

              {selectedProvider === "ollama" && (
                <div>
                  <h3 style={{ marginBottom: "1.5rem", color: "#fff", fontSize: "1.1rem" }}>Ollama Configuration</h3>
                  <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Ollama Endpoint</label>
                      <input 
                        type="text" 
                        required
                        value={ollamaEndpoint} 
                        onChange={(e) => setOllamaEndpoint(e.target.value)} 
                        placeholder="http://localhost:11434/v1"
                        style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "#fff" }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Model Name (e.g. llama3)</label>
                      <input 
                        type="text" 
                        required
                        value={ollamaModel} 
                        onChange={(e) => setOllamaModel(e.target.value)} 
                        placeholder="llama3"
                        style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "#fff" }}
                      />
                    </div>
                  </div>
                </div>
              )}

              {selectedProvider === "codex" && (
                <div>
                  <h3 style={{ marginBottom: "1.5rem", color: "#fff", fontSize: "1.1rem" }}>Codex WebSocket Server</h3>
                  <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Codex Endpoint URL</label>
                      <input 
                        type="text" 
                        required
                        value={codexEndpoint} 
                        onChange={(e) => setCodexEndpoint(e.target.value)} 
                        placeholder="ws://127.0.0.1:4500"
                        style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "#fff" }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Codex Model (optional)</label>
                      <input 
                        type="text" 
                        value={codexModel} 
                        onChange={(e) => setCodexModel(e.target.value)} 
                        placeholder="gpt-4o"
                        style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "#fff" }}
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end" }}>
              <button 
                type="submit" 
                disabled={saving} 
                className="btn btn-primary"
                style={{ minWidth: "150px" }}
              >
                {saving ? "Configuring..." : "Save and Continue"}
              </button>
            </div>
          </form>
        </div>
      </div>
    );
  }

  return <SyncProvider>{children}</SyncProvider>;
}
