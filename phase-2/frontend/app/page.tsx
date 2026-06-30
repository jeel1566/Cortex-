"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";

export default function DashboardPage() {
  const { getToken, userId, isLoaded, isSignedIn } = useAuth();
  const [loading, setLoading] = useState(true);
  
  // Dashboard states
  const [pagesCount, setPagesCount] = useState(0);
  const [activeSources, setActiveSources] = useState(0);
  const [notionEnabled, setNotionEnabled] = useState(false);
  const [slackEnabled, setSlackEnabled] = useState(false);

  // Ingestion syncing states
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState("");
  const [syncStatus, setSyncStatus] = useState<"idle" | "running" | "done" | "error">("idle");

  // Query states
  const [question, setQuestion] = useState("");
  const [queryDepartment, setQueryDepartment] = useState("Engineering");
  const [queryClearance, setQueryClearance] = useState("team");
  const [queryResult, setQueryResult] = useState<any>(null);
  const [queryLoading, setQueryLoading] = useState(false);

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

  const fetchDashboardMetrics = async () => {
    try {
      const token = await getAuthToken();
      
      const pagesRes = await fetch("http://127.0.0.1:8000/v1/pages", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (pagesRes.ok) {
        const pagesData = await pagesRes.json();
        const realPages = pagesData.filter((p: any) => p.id !== "README");
        setPagesCount(realPages.length);
      }

      const settingsRes = await fetch("http://127.0.0.1:8000/v1/settings", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (settingsRes.ok) {
        const settingsData = await settingsRes.json();
        let sourcesCount = 0;
        if (settingsData.connectors) {
          if (settingsData.connectors.notion?.enabled) {
            sourcesCount += 1;
            setNotionEnabled(true);
          } else {
            setNotionEnabled(false);
          }
          if (settingsData.connectors.slack?.enabled) {
            sourcesCount += 1;
            setSlackEnabled(true);
          } else {
            setSlackEnabled(false);
          }
        }
        setActiveSources(sourcesCount);
      }
    } catch (e) {
      console.error("Error loading dashboard metrics:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardMetrics();
  }, [isLoaded, isSignedIn]);

  const triggerSyncAll = async () => {
    setSyncing(true);
    setSyncStatus("running");
    setSyncMessage("Starting Notion sync connector...");
    
    try {
      const token = await getAuthToken();
      
      // Start Notion
      let notionJobId = null;
      if (notionEnabled) {
        const notionRes = await fetch("http://127.0.0.1:8000/v1/connectors/notion/sync", {
          method: "POST",
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (notionRes.ok) {
          const notionData = await notionRes.json();
          notionJobId = notionData.job_id;
        }
      }
      
      // Start Slack
      let slackJobId = null;
      if (slackEnabled) {
        const slackRes = await fetch("http://127.0.0.1:8000/v1/connectors/slack/sync", {
          method: "POST",
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (slackRes.ok) {
          const slackData = await slackRes.json();
          slackJobId = slackData.job_id;
        }
      }

      setSyncStatus("done");
      setSyncMessage("Sync triggered for enabled connectors in the background!");
      fetchDashboardMetrics();
      setTimeout(() => {
        setSyncing(false);
        setSyncStatus("idle");
        setSyncMessage("");
      }, 5000);
    } catch (e) {
      setSyncStatus("error");
      setSyncMessage("Error connecting to backend compiler.");
      setSyncing(false);
    }
  };

  const handleQuery = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;

    setQueryLoading(true);
    setQueryResult(null);

    // Map query clearance level to index number for permission checks
    const clearanceMap: Record<string, number> = {
      "public": 0,
      "team": 1,
      "confidential": 2,
      "restricted": 3
    };
    const authorityLevel = clearanceMap[queryClearance] ?? 1;

    try {
      // Setup payload representing the requesting agent authority & department
      const mockPayload = {
        tenant_id: userId || "tenant_a",
        authority_level: authorityLevel,
        department: queryDepartment,
        role: "member",
        name: "Mock Agent Context"
      };
      const token = btoa(JSON.stringify(mockPayload));

      const res = await fetch("http://127.0.0.1:8000/v1/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ question: question })
      });

      if (res.ok) {
        const data = await res.json();
        setQueryResult(data);
      } else {
        alert("Query failed to run on backend.");
      }
    } catch (e) {
      console.error(e);
      alert("Error connecting to query engine.");
    } finally {
      setQueryLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "50vh", color: "var(--text-secondary)" }}>
        <div>
          <div style={{ width: "45px", height: "45px", border: "3px solid var(--border)", borderTopColor: "var(--accent)", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 1.25rem" }}></div>
          <div style={{ fontSize: "1.1rem", fontWeight: 600 }}>Loading dashboard metrics...</div>
          <style dangerouslySetInnerHTML={{ __html: `@keyframes spin { to { transform: rotate(360deg); } }` }} />
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="header-title">Cortex Dashboard</h1>
      <p className="header-subtitle">Knowledge Operating System monitor & permission-aware compiler client.</p>

      {/* Metric counters */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "1.5rem", marginBottom: "3rem" }}>
        <div className="card">
          <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", textTransform: "uppercase", marginBottom: "0.5rem" }}>
            Total Pages Ingested
          </div>
          <div style={{ fontSize: "2.5rem", fontWeight: 700, fontFamily: "var(--font-display)" }}>
            {pagesCount}
          </div>
        </div>
        <div className="card">
          <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", textTransform: "uppercase", marginBottom: "0.5rem" }}>
            Active Target Sources
          </div>
          <div style={{ fontSize: "2.5rem", fontWeight: 700, fontFamily: "var(--font-display)", color: "var(--accent)" }}>
            {activeSources} {activeSources === 1 ? "Source" : "Sources"}
          </div>
        </div>
        <div className="card">
          <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", textTransform: "uppercase", marginBottom: "0.5rem" }}>
            Notion & Slack Status
          </div>
          <div style={{ fontSize: "1.1rem", fontWeight: 600, marginTop: "0.5rem", color: "var(--text-primary)" }}>
            Notion: {notionEnabled ? "Active" : "Off"} | Slack: {slackEnabled ? "Active" : "Off"}
          </div>
        </div>
      </div>

      {/* Main Dashboard Rows */}
      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 0.8fr", gap: "2rem", alignItems: "start", marginBottom: "3rem" }}>
        
        {/* LEFT COLUMN: KNOWLEDGE OS SECURE SEARCH */}
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div>
            <h2 style={{ fontSize: "1.5rem" }}>Trusted Knowledge OS Search</h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", marginTop: "0.15rem" }}>
              Verify credential-based redaction and proposition coverage.
            </p>
          </div>

          <form onSubmit={handleQuery} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {/* Context Filters */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              <div>
                <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "0.35rem" }}>Requesting Department</label>
                <select 
                  value={queryDepartment} 
                  onChange={(e) => setQueryDepartment(e.target.value)}
                  style={{ width: "100%", padding: "0.6rem", background: "var(--bg-tertiary)", border: "1px solid var(--border)", borderRadius: "6px", color: "#fff" }}
                >
                  <option value="Engineering">Engineering</option>
                  <option value="Sales">Sales</option>
                  <option value="HR">Human Resources (HR)</option>
                  <option value="Finance">Finance</option>
                </select>
              </div>
              
              <div>
                <label style={{ display: "block", fontSize: "0.8rem", color: "var(--text-secondary)", marginBottom: "0.35rem" }}>Clearance Level</label>
                <select 
                  value={queryClearance} 
                  onChange={(e) => setQueryClearance(e.target.value)}
                  style={{ width: "100%", padding: "0.6rem", background: "var(--bg-tertiary)", border: "1px solid var(--border)", borderRadius: "6px", color: "#fff" }}
                >
                  <option value="public">Public</option>
                  <option value="team">Team (Standard)</option>
                  <option value="confidential">Confidential</option>
                  <option value="restricted">Restricted (L5 Admin)</option>
                </select>
              </div>
            </div>

            {/* Input & button */}
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <input 
                type="text" 
                placeholder="Ask corporate knowledge base (e.g. What is our target NPS?)..." 
                value={question} 
                onChange={(e) => setQuestion(e.target.value)}
                style={{ flex: 1, padding: "0.75rem 1rem", background: "var(--bg-primary)", border: "1px solid var(--border)", borderRadius: "6px", color: "#fff" }}
              />
              <button type="submit" disabled={queryLoading} className="btn btn-primary" style={{ padding: "0 1.5rem" }}>
                {queryLoading ? "Searching..." : "Query"}
              </button>
            </div>
          </form>

          {/* Results Panel */}
          {queryResult && (
            <div style={{ background: "rgba(255,255,255,0.01)", border: "1px solid var(--border)", borderRadius: "8px", padding: "1.5rem", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
              <div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                  <h3 style={{ fontSize: "1.1rem" }}>Answer Response</h3>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                    Confidence: {(queryResult.confidence * 100).toFixed(0)}% • Latency: {queryResult.latency_ms}ms
                  </span>
                </div>
                <div style={{ fontSize: "0.95rem", lineHeight: "1.6", color: "var(--text-primary)" }}>
                  {queryResult.answer}
                </div>
              </div>

              {/* Citations */}
              <div>
                <h4 style={{ fontSize: "0.9rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>Citations & Verified Evidence</h4>
                {queryResult.citations && queryResult.citations.length > 0 ? (
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    {queryResult.citations.map((c: string, idx: number) => (
                      <span key={idx} style={{ padding: "0.35rem 0.6rem", background: "var(--accent-green)", border: "1px solid var(--accent)", borderRadius: "4px", fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "var(--text-primary)" }}>
                        {c}
                      </span>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>No verified citations used.</div>
                )}
              </div>

              {/* Redactions list */}
              {queryResult.redactions && queryResult.redactions.length > 0 && (
                <div>
                  <h4 style={{ fontSize: "0.9rem", color: "var(--error)", marginBottom: "0.5rem" }}>🛡️ Redacted Items (Insufficient Credentials)</h4>
                  <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                    {queryResult.redactions.map((r: string, idx: number) => (
                      <span key={idx} style={{ padding: "0.35rem 0.6rem", background: "rgba(207,102,102,0.1)", border: "1px solid rgba(207,102,102,0.2)", borderRadius: "4px", fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "var(--error)" }}>
                        {r}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* RIGHT COLUMN: REPOSITORY INGEST CONTROL */}
        <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          
          {/* Ingest Card */}
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
            <div>
              <h2 style={{ fontSize: "1.35rem" }}>Ingestion Pipeline</h2>
              <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>Sync enabled Notion and Slack sources immediately.</p>
            </div>

            <button 
              onClick={triggerSyncAll} 
              disabled={syncing}
              className="btn btn-primary" 
              style={{ width: "100%", padding: "0.9rem" }}
            >
              {syncing ? "⏳ Syncing..." : "🔄 Sync Target Sources"}
            </button>

            {syncMessage && (
              <div style={{
                padding: "0.75rem 1rem", 
                borderRadius: "8px", 
                fontSize: "0.82rem",
                background: syncStatus === "done" ? "rgba(99, 168, 124, 0.1)" : syncStatus === "error" ? "rgba(207, 102, 102, 0.1)" : "rgba(255,255,255,0.03)",
                border: `1px solid ${syncStatus === "done" ? "rgba(99, 168, 124, 0.2)" : syncStatus === "error" ? "rgba(207, 102, 102, 0.2)" : "var(--border)"}`,
                color: syncStatus === "done" ? "var(--success)" : syncStatus === "error" ? "var(--error)" : "var(--text-primary)"
              }}>
                {syncMessage}
              </div>
            )}
          </div>

          {/* Quick Actions Card */}
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <h2 style={{ fontSize: "1.35rem", marginBottom: "0.25rem" }}>Destinations</h2>
            <a href="/inbox" className="btn btn-outline" style={{ textDecoration: "none", textAlign: "center" }}>
              Inbox (Review Drafts)
            </a>
            <a href="/explorer" className="btn btn-outline" style={{ textDecoration: "none", textAlign: "center" }}>
              Explorer (Knowledge Map)
            </a>
            <a href="/settings" className="btn btn-outline" style={{ textDecoration: "none", textAlign: "center" }}>
              Settings (AI / Keys)
            </a>
          </div>
        </div>

      </div>
    </div>
  );
}
