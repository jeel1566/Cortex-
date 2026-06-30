"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";

export default function SettingsPage() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Syncing states
  const [syncStatus, setSyncStatus] = useState<"idle" | "syncing" | "done" | "error">("idle");
  const [syncMessage, setSyncMessage] = useState<string>("");

  // Active Tab
  const [activeTab, setActiveTab] = useState<"ai" | "notion" | "slack" | "upload">("ai");

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

  // Upload States
  const [uploadStatus, setUploadStatus] = useState<"idle" | "uploading" | "done" | "error">("idle");
  const [uploadMessage, setUploadMessage] = useState<string>("");

  const getAuthToken = async () => {
    if (process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) {
      try {
        const token = await getToken();
        if (token) return token;
      } catch (e) {
        console.warn("Clerk token acquisition failed, using fallback.", e);
      }
    }
    const mockPayload = { tenant_id: "tenant_a", authority_level: 5, name: "Admin (Mock Tenant)" };
    return btoa(JSON.stringify(mockPayload));
  };

  const fetchSettings = async () => {
    setLoading(true);
    setError(null);
    try {
      const token = await getAuthToken();
      const res = await fetch("http://127.0.0.1:8000/v1/settings", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
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

  const pollJobStatus = async (jobId: string, token: string) => {
    const intervalId = setInterval(async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/v1/sync-runs/${jobId}`, {
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          const status = data.status;
          
          if (status === "completed") {
            setSyncStatus("done");
            setUploadStatus("done");
            const counts = data.counts || {};
            const msg = `✓ Ingestion completed! Processed ${counts.objects || 0} objects, generated ${counts.drafts || 0} drafts.`;
            setSyncMessage(msg);
            setUploadMessage(msg);
            clearInterval(intervalId);
            fetchSettings();
            setTimeout(() => {
              setSyncStatus("idle");
              setSyncMessage("");
              setUploadStatus("idle");
              setUploadMessage("");
            }, 8000);
          } else if (status === "failed") {
            const err = data.error_message || "Processing failed.";
            setSyncStatus("error");
            setUploadStatus("error");
            setSyncMessage(`Sync failed: ${err}`);
            setUploadMessage(`Processing failed: ${err}`);
            clearInterval(intervalId);
          } else {
            const progressMsg = `Ingestion pipeline running for ${data.connector_type}...`;
            setSyncMessage(progressMsg);
            setUploadMessage(progressMsg);
          }
        }
      } catch (e) {
        console.error("Error polling sync status:", e);
      }
    }, 1500);
  };

  const triggerSync = async (type: string) => {
    setSyncStatus("syncing");
    setSyncMessage(`Initializing ${type} synchronization...`);
    try {
      const token = await getAuthToken();
      const res = await fetch(`http://127.0.0.1:8000/v1/connectors/${type}/sync`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` }
      });
      const data = await res.json();
      if (res.ok) {
        pollJobStatus(data.job_id, token);
      } else {
        setSyncStatus("error");
        setSyncMessage(data.detail || "Sync failed to start.");
      }
    } catch (e: any) {
      setSyncStatus("error");
      setSyncMessage("Could not reach backend server.");
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    
    setUploadStatus("uploading");
    setUploadMessage(`Uploading ${file.name}...`);
    
    try {
      const token = await getAuthToken();
      const formData = new FormData();
      formData.append("file", file);
      
      const res = await fetch("http://127.0.0.1:8000/v1/uploads", {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` },
        body: formData
      });
      
      if (res.ok) {
        const data = await res.json();
        pollJobStatus(data.job_id, token);
      } else {
        const err = await res.json();
        setUploadStatus("error");
        setUploadMessage(`Upload failed: ${err.detail || "Unknown error"}`);
      }
    } catch (err: any) {
      setUploadStatus("error");
      setUploadMessage(`Upload error: ${err.message || "Failed to reach backend"}`);
    }
  };

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
      return new Date(isoStr).toLocaleString();
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
      <p className="header-subtitle">Manage AI providers, targeting criteria, and target synchronization connectors.</p>

      {success && (
        <div style={{ background: "rgba(99, 168, 124, 0.1)", border: "1px solid rgba(99, 168, 124, 0.2)", color: "var(--success)", padding: "1rem", borderRadius: "8px", marginBottom: "2rem", fontSize: "0.9rem" }}>
          ✓ Settings and connector configurations updated successfully!
        </div>
      )}

      {error && (
        <div style={{ background: "rgba(207, 102, 102, 0.1)", border: "1px solid rgba(207, 102, 102, 0.2)", color: "var(--error)", padding: "1rem", borderRadius: "8px", marginBottom: "2rem", fontSize: "0.9rem" }}>
          {error}
        </div>
      )}

      {/* Tabs */}
      <div style={{ display: "flex", borderBottom: "1px solid var(--border)", marginBottom: "2rem", gap: "1.5rem" }}>
        <button
          type="button"
          onClick={() => setActiveTab("ai")}
          style={{
            background: "none",
            border: "none",
            borderBottom: activeTab === "ai" ? "2px solid var(--accent)" : "2px solid transparent",
            color: activeTab === "ai" ? "var(--text-primary)" : "var(--text-secondary)",
            padding: "0.75rem 0.5rem",
            fontSize: "1rem",
            fontWeight: 600,
            cursor: "pointer"
          }}
        >
          🤖 AI Engine Provider
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("notion")}
          style={{
            background: "none",
            border: "none",
            borderBottom: activeTab === "notion" ? "2px solid var(--accent)" : "2px solid transparent",
            color: activeTab === "notion" ? "var(--text-primary)" : "var(--text-secondary)",
            padding: "0.75rem 0.5rem",
            fontSize: "1rem",
            fontWeight: 600,
            cursor: "pointer"
          }}
        >
          📓 Notion Sync
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("slack")}
          style={{
            background: "none",
            border: "none",
            borderBottom: activeTab === "slack" ? "2px solid var(--accent)" : "2px solid transparent",
            color: activeTab === "slack" ? "var(--text-primary)" : "var(--text-secondary)",
            padding: "0.75rem 0.5rem",
            fontSize: "1rem",
            fontWeight: 600,
            cursor: "pointer"
          }}
        >
          💬 Slack Sync
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("upload")}
          style={{
            background: "none",
            border: "none",
            borderBottom: activeTab === "upload" ? "2px solid var(--accent)" : "2px solid transparent",
            color: activeTab === "upload" ? "var(--text-primary)" : "var(--text-secondary)",
            padding: "0.75rem 0.5rem",
            fontSize: "1rem",
            fontWeight: 600,
            cursor: "pointer"
          }}
        >
          📁 Local Upload
        </button>
      </div>

      <div className="card" style={{ padding: "2.5rem 2rem", borderRadius: "14px" }}>
        <form onSubmit={handleSave}>
          
          {activeTab === "ai" && (
            <div>
              <h2 style={{ fontSize: "1.35rem", marginBottom: "1.5rem" }}>AI Model Provider</h2>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem", marginBottom: "2rem" }}>
                <div 
                  onClick={() => setSelectedProvider("web_api")}
                  style={{ 
                    cursor: "pointer", padding: "1.25rem", borderRadius: "10px", 
                    background: selectedProvider === "web_api" ? "var(--accent-green)" : "var(--bg-tertiary)", 
                    border: selectedProvider === "web_api" ? "2px solid var(--accent)" : "1px solid var(--border)",
                    textAlign: "center"
                  }}
                >
                  <div style={{ fontSize: "1.75rem", marginBottom: "0.35rem" }}>🌐</div>
                  <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>Web API</div>
                </div>

                <div 
                  onClick={() => setSelectedProvider("ollama")}
                  style={{ 
                    cursor: "pointer", padding: "1.25rem", borderRadius: "10px", 
                    background: selectedProvider === "ollama" ? "var(--accent-green)" : "var(--bg-tertiary)", 
                    border: selectedProvider === "ollama" ? "2px solid var(--accent)" : "1px solid var(--border)",
                    textAlign: "center"
                  }}
                >
                  <div style={{ fontSize: "1.75rem", marginBottom: "0.35rem" }}>🦙</div>
                  <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>Ollama</div>
                </div>

                <div 
                  onClick={() => setSelectedProvider("codex")}
                  style={{ 
                    cursor: "pointer", padding: "1.25rem", borderRadius: "10px", 
                    background: selectedProvider === "codex" ? "var(--accent-green)" : "var(--bg-tertiary)", 
                    border: selectedProvider === "codex" ? "2px solid var(--accent)" : "1px solid var(--border)",
                    textAlign: "center"
                  }}
                >
                  <div style={{ fontSize: "1.75rem", marginBottom: "0.35rem" }}>💻</div>
                  <div style={{ fontWeight: 600, fontSize: "0.95rem" }}>Codex CLI</div>
                </div>
              </div>

              <div style={{ background: "var(--bg-tertiary)", padding: "2rem", borderRadius: "10px", border: "1px solid var(--border)" }}>
                {selectedProvider === "web_api" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>API Endpoint URL</label>
                      <input 
                        type="text" required value={webApiEndpoint} onChange={(e) => setWebApiEndpoint(e.target.value)} 
                        placeholder="https://api.groq.com/openai/v1"
                        style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "var(--text-primary)" }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>API Key</label>
                      <input 
                        type="password" required value={webApiKey} onChange={(e) => setWebApiKey(e.target.value)} 
                        placeholder="••••••••••••••••"
                        style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "var(--text-primary)" }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Model Name</label>
                      <input 
                        type="text" required value={webApiModel} onChange={(e) => setWebApiModel(e.target.value)} 
                        placeholder="llama-3.1-8b-instant"
                        style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "var(--text-primary)" }}
                      />
                    </div>
                  </div>
                )}

                {selectedProvider === "ollama" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Ollama Endpoint</label>
                      <input 
                        type="text" required value={ollamaEndpoint} onChange={(e) => setOllamaEndpoint(e.target.value)} 
                        placeholder="http://localhost:11434/v1"
                        style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "var(--text-primary)" }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Model Name</label>
                      <input 
                        type="text" required value={ollamaModel} onChange={(e) => setOllamaModel(e.target.value)} 
                        placeholder="llama3"
                        style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "var(--text-primary)" }}
                      />
                    </div>
                  </div>
                )}

                {selectedProvider === "codex" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                    <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Codex Endpoint URL</label>
                      <input 
                        type="text" required value={codexEndpoint} onChange={(e) => setCodexEndpoint(e.target.value)} 
                        placeholder="ws://127.0.0.1:4500"
                        style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "var(--text-primary)" }}
                      />
                    </div>
                    <div>
                      <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Codex Model Name (optional)</label>
                      <input 
                        type="text" value={codexModel} onChange={(e) => setCodexModel(e.target.value)} 
                        placeholder="gpt-4o"
                        style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "var(--text-primary)" }}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === "notion" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h2 style={{ fontSize: "1.35rem" }}>Notion Sync Connector</h2>
                  <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                    Polls a Notion workspace to ingest updates automatically.
                  </p>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{ fontSize: "0.85rem", fontWeight: 600, color: notionEnabled ? "var(--success)" : "var(--text-secondary)" }}>
                    {notionEnabled ? "Sync Active" : "Sync Disabled"}
                  </span>
                  <input
                    type="checkbox" checked={notionEnabled} onChange={(e) => setNotionEnabled(e.target.checked)}
                    style={{ cursor: "pointer", width: "18px", height: "18px" }}
                  />
                </div>
              </div>

              <div style={{ background: "var(--bg-tertiary)", padding: "1.5rem", borderRadius: "12px", border: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Notion Integration Token (API Key)</label>
                  <input 
                    type="password" value={notionApiKey} onChange={(e) => setNotionApiKey(e.target.value)} 
                    placeholder="Enter integration token (secret_...)" required={notionEnabled}
                    style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--text-primary)" }}
                  />
                </div>

                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Notion Database ID (optional)</label>
                  <input 
                    type="text" value={notionDatabaseId} onChange={(e) => setNotionDatabaseId(e.target.value)} 
                    placeholder="Database ID"
                    style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--text-primary)" }}
                  />
                </div>

                <div style={{ borderTop: "1px solid var(--border)", paddingTop: "1.25rem" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem" }}>
                    <div>
                      <div style={{ fontSize: "0.9rem", fontWeight: 600, marginBottom: "0.25rem" }}>Manual Sync</div>
                      <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>Pull all Notion pages into Cortex right now</div>
                    </div>
                    <button
                      type="button" onClick={() => triggerSync("notion")} disabled={syncStatus === "syncing"}
                      className="btn btn-primary"
                    >
                      {syncStatus === "syncing" ? "⏳ Syncing..." : "🔄 Sync Now"}
                    </button>
                  </div>
                  {syncMessage && (
                    <div style={{ marginTop: "0.75rem", padding: "0.75rem", borderRadius: "6px", fontSize: "0.82rem", background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)" }}>
                      {syncMessage}
                    </div>
                  )}
                </div>

                <div style={{ borderTop: "1px solid var(--border)", paddingTop: "1.25rem", display: "flex", justifyContent: "space-between" }}>
                  <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Last Synchronization:</span>
                  <span style={{ fontSize: "0.85rem", fontWeight: 600 }}>{formatDate(notionLastPolled)}</span>
                </div>
              </div>
            </div>
          )}

          {activeTab === "slack" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <h2 style={{ fontSize: "1.35rem" }}>Slack Sync Connector</h2>
                  <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                    Ingests conversations from targeted Slack channels.
                  </p>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                  <span style={{ fontSize: "0.85rem", fontWeight: 600, color: slackEnabled ? "var(--success)" : "var(--text-secondary)" }}>
                    {slackEnabled ? "Sync Active" : "Sync Disabled"}
                  </span>
                  <input
                    type="checkbox" checked={slackEnabled} onChange={(e) => setSlackEnabled(e.target.checked)}
                    style={{ cursor: "pointer", width: "18px", height: "18px" }}
                  />
                </div>
              </div>

              <div style={{ background: "var(--bg-tertiary)", padding: "1.5rem", borderRadius: "12px", border: "1px solid var(--border)", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Slack Bot User OAuth Token</label>
                  <input 
                    type="password" value={slackToken} onChange={(e) => setSlackToken(e.target.value)} 
                    placeholder="xoxb-..." required={slackEnabled}
                    style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--text-primary)" }}
                  />
                </div>
                
                <div>
                  <label style={{ display: "block", fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Target Channel</label>
                  <input 
                    type="text" value={slackChannel} onChange={(e) => setSlackChannel(e.target.value)} 
                    placeholder="general" required={slackEnabled}
                    style={{ width: "100%", padding: "0.75rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "8px", color: "var(--text-primary)" }}
                  />
                </div>

                <div style={{ borderTop: "1px solid var(--border)", paddingTop: "1.25rem" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "1rem" }}>
                    <div>
                      <div style={{ fontSize: "0.9rem", fontWeight: 600, marginBottom: "0.25rem" }}>Manual Slack Sync</div>
                      <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>Pull Slack channel messages into Cortex right now</div>
                    </div>
                    <button
                      type="button" onClick={() => triggerSync("slack")} disabled={syncStatus === "syncing"}
                      className="btn btn-primary"
                    >
                      {syncStatus === "syncing" ? "⏳ Syncing..." : "🔄 Sync Now"}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === "upload" && (
            <div>
              <h2 style={{ fontSize: "1.35rem", marginBottom: "0.5rem" }}>Local File Upload</h2>
              <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "1.5rem" }}>
                Upload files (Markdown, TXT, PDF, Word DOCX, CSV/Excel) to compile them into page drafts immediately.
              </p>
              
              <div style={{
                border: "2px dashed var(--border)",
                borderRadius: "12px",
                padding: "3rem 2rem",
                textAlign: "center",
                background: "rgba(255,255,255,0.01)",
                cursor: "pointer",
                position: "relative",
                transition: "all 0.2s ease"
              }}>
                <input 
                  type="file" 
                  onChange={handleFileUpload} 
                  style={{
                    position: "absolute",
                    inset: 0,
                    opacity: 0,
                    cursor: "pointer"
                  }} 
                />
                <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>📥</div>
                <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>Click or Drag File Here to Upload</div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Supports .md, .txt, .pdf, .docx, .csv, .xlsx</div>
              </div>
              
              {uploadMessage && (
                <div style={{
                  marginTop: "1.5rem",
                  padding: "1rem",
                  borderRadius: "8px",
                  fontSize: "0.85rem",
                  background: "rgba(255,255,255,0.02)",
                  border: "1px solid var(--border)"
                }}>
                  {uploadMessage}
                </div>
              )}
            </div>
          )}

          {activeTab !== "upload" && (
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "2rem", borderTop: "1px solid var(--border)", paddingTop: "1.5rem" }}>
              <button 
                type="submit" disabled={saving} className="btn btn-primary" style={{ minWidth: "150px" }}
              >
                {saving ? "Saving..." : "Save Settings"}
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  );
}
