"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";

export default function SettingsPage() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Active Tab
  const [activeTab, setActiveTab] = useState<"ai" | "notion" | "slack">("ai");

  // Form states - AI
  const [selectedProvider, setSelectedProvider] = useState<"ollama" | "web_api" | "codex">("web_api");
  const [ollamaEndpoint, setOllamaEndpoint] = useState("http://localhost:11434/v1");
  const [ollamaModel, setOllamaModel] = useState("llama3");
  const [webApiEndpoint, setWebApiEndpoint] = useState("");
  const [webApiKey, setWebApiKey] = useState("");
  const [webApiModel, setWebApiModel] = useState("llama-3.1-8b-instant");
  const [codexEndpoint, setCodexEndpoint] = useState("ws://127.0.0.1:4500");
  const [codexModel, setCodexModel] = useState("");

  // Form states - Notion
  const [notionEnabled, setNotionEnabled] = useState(false);
  const [notionDatabaseId, setNotionDatabaseId] = useState("");
  const [notionApiKey, setNotionApiKey] = useState("");
  const [notionLastPolled, setNotionLastPolled] = useState("");

  // Form states - Slack
  const [slackEnabled, setSlackEnabled] = useState(false);
  const [slackToken, setSlackToken] = useState("");
  const [slackChannel, setSlackChannel] = useState("");

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
    setError(null);
    try {
      const token = await getAuthToken();
      const res = await fetch("http://127.0.0.1:8000/v1/settings", {
        headers: {
          "Authorization": `Bearer ${token}`
        }
      });
      if (res.ok) {
        const data = await res.json();
        
        // AI Provider Settings
        if (data.ai_provider && data.ai_provider !== "not_configured") {
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

        // Connectors Settings
        if (data.connectors) {
          const notion = data.connectors.notion;
          if (notion) {
            setNotionEnabled(notion.enabled ?? false);
            setNotionDatabaseId(notion.database_id ?? "");
            setNotionApiKey(notion.api_key ?? "");
            setNotionLastPolled(notion.last_polled ?? "");
          }
          const slack = data.connectors.slack;
          if (slack) {
            setSlackEnabled(slack.enabled ?? false);
            setSlackToken(slack.token ?? "");
            setSlackChannel(slack.channel ?? "");
          }
        }
      } else {
        throw new Error("Failed to load settings from server.");
      }
    } catch (e: any) {
      console.error(e);
      setError("Unable to load configurations. Please check backend connection.");
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
    setSuccess(false);

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

    const connectors = {
      notion: {
        enabled: notionEnabled,
        database_id: notionDatabaseId,
        api_key: notionApiKey
      },
      slack: {
        enabled: slackEnabled,
        token: slackToken,
        channel: slackChannel
      }
    };

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
          config: config,
          connectors: connectors
        })
      });

      if (res.ok) {
        setSuccess(true);
        // Refresh to fetch masked credentials and latest fields
        await fetchSettings();
        setTimeout(() => setSuccess(false), 4000);
      } else {
        const errData = await res.json();
        setError(errData.detail || "Failed to save settings.");
      }
    } catch (err: any) {
      setError(err.message || "Failed to update configurations.");
    } finally {
      setSaving(false);
    }
  };

  const formatDate = (isoStr: string) => {
    if (!isoStr) return "Never synced";
    try {
      const date = new Date(isoStr);
      return date.toLocaleString();
    } catch (e) {
      return isoStr;
    }
  };

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "50vh", color: "var(--text-secondary)" }}>
        <div>
          <div style={{ width: "45px", height: "45px", border: "3px solid var(--border)", borderTopColor: "var(--accent)", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 1.25rem" }}></div>
          <div style={{ fontSize: "1.1rem", fontWeight: 600 }}>Loading active settings...</div>
          <style dangerouslySetInnerHTML={{ __html: `@keyframes spin { to { transform: rotate(360deg); } }` }} />
        </div>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: "850px" }}>
      <h1 className="header-title">Settings</h1>
      <p className="header-subtitle">Manage AI engine configurations, model parameters, and data source connectors.</p>

      {success && (
        <div style={{ background: "rgba(16, 185, 129, 0.1)", border: "1px solid rgba(16, 185, 129, 0.2)", color: "var(--success)", padding: "1rem", borderRadius: "8px", marginBottom: "2rem", fontSize: "0.9rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <span>✓</span> Settings and connector configurations updated successfully!
        </div>
      )}

      {error && (
        <div style={{ background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.2)", color: "var(--error)", padding: "1rem", borderRadius: "8px", marginBottom: "2rem", fontSize: "0.9rem" }}>
          {error}
        </div>
      )}

      {/* Main Settings Navigation Tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid var(--border)", marginBottom: "2rem", gap: "1.5rem" }}>
        <button
          onClick={() => setActiveTab("ai")}
          style={{
            background: "none",
            border: "none",
            borderBottom: activeTab === "ai" ? "2px solid var(--accent)" : "2px solid transparent",
            color: activeTab === "ai" ? "#fff" : "var(--text-secondary)",
            padding: "0.75rem 0.5rem",
            fontSize: "1rem",
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 0.2s ease"
          }}
        >
          🤖 AI Engine Provider
        </button>
        <button
          onClick={() => setActiveTab("notion")}
          style={{
            background: "none",
            border: "none",
            borderBottom: activeTab === "notion" ? "2px solid var(--accent)" : "2px solid transparent",
            color: activeTab === "notion" ? "#fff" : "var(--text-secondary)",
            padding: "0.75rem 0.5rem",
            fontSize: "1rem",
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 0.2s ease"
          }}
        >
          📓 Notion Sync
        </button>
        <button
          onClick={() => setActiveTab("slack")}
          style={{
            background: "none",
            border: "none",
            borderBottom: activeTab === "slack" ? "2px solid var(--accent)" : "2px solid transparent",
            color: activeTab === "slack" ? "#fff" : "var(--text-secondary)",
            padding: "0.75rem 0.5rem",
            fontSize: "1rem",
            fontWeight: 600,
            cursor: "pointer",
            transition: "all 0.2s ease"
          }}
        >
          💬 Slack Sync
        </button>
      </div>

      <div className="card" style={{ padding: "2.5rem 2rem", borderRadius: "14px" }}>
        <form onSubmit={handleSave}>
          
          {/* TAB 1: AI ENGINE PROVIDER */}
          {activeTab === "ai" && (
            <div>
              <h2 style={{ fontSize: "1.35rem", marginBottom: "1.5rem", color: "#fff" }}>AI Model Provider</h2>
              
              {/* Provider cards */}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem", marginBottom: "2rem" }}>
                <div 
                  onClick={() => setSelectedProvider("web_api")}
                  style={{ 
                    cursor: "pointer", 
                    padding: "1.25rem", 
                    borderRadius: "10px", 
                    background: selectedProvider === "web_api" ? "rgba(99, 102, 241, 0.08)" : "var(--bg-tertiary)", 
                    border: selectedProvider === "web_api" ? "2px solid var(--accent)" : "1px solid var(--border)",
                    transition: "all 0.2s ease",
                    textAlign: "center"
                  }}
                >
                  <div style={{ fontSize: "1.75rem", marginBottom: "0.35rem" }}>🌐</div>
                  <div style={{ fontWeight: 600, color: "#fff", fontSize: "0.95rem" }}>Web API</div>
                </div>

                <div 
                  onClick={() => setSelectedProvider("ollama")}
                  style={{ 
                    cursor: "pointer", 
                    padding: "1.25rem", 
                    borderRadius: "10px", 
                    background: selectedProvider === "ollama" ? "rgba(99, 102, 241, 0.08)" : "var(--bg-tertiary)", 
                    border: selectedProvider === "ollama" ? "2px solid var(--accent)" : "1px solid var(--border)",
                    transition: "all 0.2s ease",
                    textAlign: "center"
                  }}
                >
                  <div style={{ fontSize: "1.75rem", marginBottom: "0.35rem" }}>🦙</div>
                  <div style={{ fontWeight: 600, color: "#fff", fontSize: "0.95rem" }}>Ollama</div>
                </div>

                <div 
                  onClick={() => setSelectedProvider("codex")}
                  style={{ 
                    cursor: "pointer", 
                    padding: "1.25rem", 
                    borderRadius: "10px", 
                    background: selectedProvider === "codex" ? "rgba(99, 102, 241, 0.08)" : "var(--bg-tertiary)", 
                    border: selectedProvider === "codex" ? "2px solid var(--accent)" : "1px solid var(--border)",
                    transition: "all 0.2s ease",
                    textAlign: "center"
                  }}
                >
                  <div style={{ fontSize: "1.75rem", marginBottom: "0.35rem" }}>💻</div>
                  <div style={{ fontWeight: 600, color: "#fff", fontSize: "0.95rem" }}>Codex CLI</div>
                </div>
              </div>

              {/* AI Details form fields */}
              <div style={{ background: "var(--bg-tertiary)", padding: "2rem", borderRadius: "10px", border: "1px solid var(--border)" }}>
                {selectedProvider === "web_api" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>API Endpoint URL</label>
                      <input 
                        type="url" 
                        required
                        value={webApiEndpoint} 
                        onChange={(e) => setWebApiEndpoint(e.target.value)} 
                        placeholder="https://api.openai.com/v1"
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
                        placeholder="Leave unchanged or enter new key"
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
                )}

                {selectedProvider === "ollama" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Ollama Endpoint</label>
                      <input 
                        type="url" 
                        required
                        value={ollamaEndpoint} 
                        onChange={(e) => setOllamaEndpoint(e.target.value)} 
                        placeholder="http://localhost:11434/v1"
                        style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "#fff" }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Model Name</label>
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
                )}

                {selectedProvider === "codex" && (
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
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Codex Model Name (optional)</label>
                      <input 
                        type="text" 
                        value={codexModel} 
                        onChange={(e) => setCodexModel(e.target.value)} 
                        placeholder="gpt-4o"
                        style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "#fff" }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 2: NOTION CONNECTOR */}
          {activeTab === "notion" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
                <div>
                  <h2 style={{ fontSize: "1.35rem", color: "#fff" }}>Notion Sync Connector</h2>
                  <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                    Polls a Notion database every 5 minutes to ingest modified pages automatically.
                  </p>
                </div>
                {/* Active switch */}
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  <span style={{ fontSize: "0.85rem", fontWeight: 600, color: notionEnabled ? "var(--success)" : "var(--text-secondary)" }}>
                    {notionEnabled ? "Sync Active" : "Sync Disabled"}
                  </span>
                  <label style={{ position: "relative", display: "inline-block", width: "48px", height: "24px" }}>
                    <input 
                      type="checkbox" 
                      checked={notionEnabled}
                      onChange={(e) => setNotionEnabled(e.target.checked)}
                      style={{ opacity: 0, width: 0, height: 0 }}
                    />
                    <span style={{
                      position: "absolute",
                      cursor: "pointer",
                      inset: 0,
                      backgroundColor: notionEnabled ? "var(--accent)" : "#3f3f46",
                      borderRadius: "24px",
                      transition: "0.2s",
                      boxShadow: notionEnabled ? "0 0 10px rgba(99, 102, 241, 0.4)" : "none"
                    }}>
                      <span style={{
                        position: "absolute",
                        content: '""',
                        height: "18px",
                        width: "18px",
                        left: notionEnabled ? "26px" : "3px",
                        bottom: "3px",
                        backgroundColor: "#fff",
                        borderRadius: "50%",
                        transition: "0.2s"
                      }} />
                    </span>
                  </label>
                </div>
              </div>

              <div style={{ background: "var(--bg-tertiary)", padding: "2rem", borderRadius: "10px", border: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Notion Integration Token (API Key)</label>
                  <input 
                    type="password" 
                    value={notionApiKey} 
                    onChange={(e) => setNotionApiKey(e.target.value)} 
                    placeholder={notionEnabled ? "Leave unchanged or enter new Notion token" : "Enter integration token (secret_...)"}
                    required={notionEnabled}
                    style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "#fff" }}
                  />
                </div>
                
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Notion Database ID</label>
                  <input 
                    type="text" 
                    value={notionDatabaseId} 
                    onChange={(e) => setNotionDatabaseId(e.target.value)} 
                    placeholder="e.g. 1a2b3c4d5e6f..."
                    required={notionEnabled}
                    style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "#fff" }}
                  />
                  <small style={{ display: "block", color: "var(--text-secondary)", fontSize: "0.75rem", marginTop: "0.35rem" }}>
                    Find this ID in the URL of your Notion database. Ensure your integration is shared with the database.
                  </small>
                </div>

                <div style={{ borderTop: "1px solid var(--border)", paddingTop: "1.25rem", marginTop: "0.5rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>
                    <span>Last Synchronization Cycle:</span>
                  </div>
                  <div style={{ fontSize: "0.85rem", fontWeight: 600, color: notionLastPolled ? "#fff" : "var(--text-secondary)" }}>
                    {formatDate(notionLastPolled)}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: SLACK CONNECTOR */}
          {activeTab === "slack" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
                <div>
                  <h2 style={{ fontSize: "1.35rem", color: "#fff" }}>Slack Sync Connector</h2>
                  <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                    Ingests messages from targeted Slack workspace channels.
                  </p>
                </div>
                {/* Active switch */}
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  <span style={{ fontSize: "0.85rem", fontWeight: 600, color: slackEnabled ? "var(--success)" : "var(--text-secondary)" }}>
                    {slackEnabled ? "Sync Active" : "Sync Disabled"}
                  </span>
                  <label style={{ position: "relative", display: "inline-block", width: "48px", height: "24px" }}>
                    <input 
                      type="checkbox" 
                      checked={slackEnabled}
                      onChange={(e) => setSlackEnabled(e.target.checked)}
                      style={{ opacity: 0, width: 0, height: 0 }}
                    />
                    <span style={{
                      position: "absolute",
                      cursor: "pointer",
                      inset: 0,
                      backgroundColor: slackEnabled ? "var(--accent)" : "#3f3f46",
                      borderRadius: "24px",
                      transition: "0.2s",
                      boxShadow: slackEnabled ? "0 0 10px rgba(99, 102, 241, 0.4)" : "none"
                    }}>
                      <span style={{
                        position: "absolute",
                        content: '""',
                        height: "18px",
                        width: "18px",
                        left: slackEnabled ? "26px" : "3px",
                        bottom: "3px",
                        backgroundColor: "#fff",
                        borderRadius: "50%",
                        transition: "0.2s"
                      }} />
                    </span>
                  </label>
                </div>
              </div>

              <div style={{ background: "var(--bg-tertiary)", padding: "2rem", borderRadius: "10px", border: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Slack Bot User OAuth Token</label>
                  <input 
                    type="password" 
                    value={slackToken} 
                    onChange={(e) => setSlackToken(e.target.value)} 
                    placeholder={slackEnabled ? "Leave unchanged or enter new Slack OAuth Token" : "Enter Slack Bot Token (xoxb-...)"}
                    required={slackEnabled}
                    style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "#fff" }}
                  />
                </div>
                
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Channel Filter / Target Channel</label>
                  <input 
                    type="text" 
                    value={slackChannel} 
                    onChange={(e) => setSlackChannel(e.target.value)} 
                    placeholder="e.g. general, C12345678"
                    required={slackEnabled}
                    style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "#fff" }}
                  />
                  <small style={{ display: "block", color: "var(--text-secondary)", fontSize: "0.75rem", marginTop: "0.35rem" }}>
                    Identify target Slack channel name or ID to index knowledge items from. Ensure the bot is added to this channel.
                  </small>
                </div>
              </div>
            </div>
          )}

          {/* Form Actions */}
          <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "2rem", borderTop: "1px solid var(--border)", paddingTop: "1.5rem" }}>
            <button 
              type="submit" 
              disabled={saving} 
              className="btn btn-primary"
              style={{ minWidth: "150px" }}
            >
              {saving ? "Saving..." : "Save Settings"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
