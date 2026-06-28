"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import { useSync } from "../components/SyncContext";

export default function DashboardPage() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [loading, setLoading] = useState(true);
  const [pagesCount, setPagesCount] = useState(0);
  const [activeSources, setActiveSources] = useState(0);
  const [notionEnabled, setNotionEnabled] = useState(false);
  const [slackEnabled, setSlackEnabled] = useState(false);

  const { syncing, syncStage, syncStatus, syncPagesCreated, syncError, startSync } = useSync();

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

  const fetchDashboardMetrics = async () => {
    try {
      const token = await getAuthToken();
      
      // 1. Fetch total pages count
      const pagesRes = await fetch("http://127.0.0.1:8000/v1/pages", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (pagesRes.ok) {
        const pagesData = await pagesRes.json();
        const realPages = pagesData.filter((p: any) => p.id !== "README");
        setPagesCount(realPages.length);
      }

      // 2. Fetch settings to determine active sync sources
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

    const handleSyncComplete = () => {
      fetchDashboardMetrics();
    };
    window.addEventListener("cortex-sync-completed", handleSyncComplete);
    return () => {
      window.removeEventListener("cortex-sync-completed", handleSyncComplete);
    };
  }, [isLoaded, isSignedIn]);

  const getStageLabel = (stage: string) => {
    const stages: Record<string, string> = {
      "initiating": "Initiating connection...",
      "queued": "Awaiting resource queue...",
      "fetching_sources": "Scanning enabled connectors...",
      "notion_fetch": "Fetching documents from Notion workspace...",
      "slack_fetch": "Retrieving threads from active Slack channels...",
      "sample_sync": "Ingesting fallback demo metadata...",
      "pii_redaction": "Redacting PII and filtering raw data logs...",
      "sentence_splitting": "Decomposing block text into propositions...",
      "speech_act_classification": "Running speech act classification model...",
      "sentence_clustering": "Clustering propositions into core decision units...",
      "page_synthesis": "Synthesizing and re-validating Markdown pages...",
      "graph_indexing": "Mapping relationships into Knowledge Graph...",
      "complete": "Pipeline execution successful!"
    };
    return stages[stage] || `Running task: ${stage}`;
  };

  const getProgressPercentage = (stage: string) => {
    const order = [
      "queued", "fetching_sources", "notion_fetch", "slack_fetch", "sample_sync",
      "pii_redaction", "sentence_splitting", "speech_act_classification",
      "sentence_clustering", "page_synthesis", "graph_indexing", "complete"
    ];
    const idx = order.indexOf(stage);
    if (idx === -1) return 5;
    return Math.round(((idx + 1) / order.length) * 100);
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
      <p className="header-subtitle">Welcome back. Monitoring corporate Knowledge OS metrics.</p>

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
            Approval Queue Size
          </div>
          <div style={{ fontSize: "2.5rem", fontWeight: 700, fontFamily: "var(--font-display)", color: "var(--warning)" }}>
            0 Pending
          </div>
        </div>
        <div className="card">
          <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", textTransform: "uppercase", marginBottom: "0.5rem" }}>
            Active Synced Sources
          </div>
          <div style={{ fontSize: "2.5rem", fontWeight: 700, fontFamily: "var(--font-display)", color: "var(--accent)" }}>
            {activeSources} {activeSources === 1 ? "Source" : "Sources"}
          </div>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem", marginBottom: "3rem", alignItems: "start" }}>
        {/* Sync Pipeline Card */}
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div>
            <h2 style={{ fontSize: "1.35rem", marginBottom: "0.25rem" }}>Live Ingestion Pipeline</h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>Trigger and monitor unified compilation across all connector integrations.</p>
          </div>

          {/* Connectors Status Indicator */}
          <div style={{ display: "flex", gap: "1rem" }}>
            <div style={{ flex: 1, backgroundColor: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", borderRadius: "8px", padding: "0.75rem 1rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.85rem", fontWeight: 500 }}>Notion Sync</span>
              <span style={{ fontSize: "0.75rem", fontWeight: 600, color: notionEnabled ? "var(--success)" : "var(--text-secondary)" }}>
                {notionEnabled ? "● Enabled" : "○ Disabled"}
              </span>
            </div>
            <div style={{ flex: 1, backgroundColor: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", borderRadius: "8px", padding: "0.75rem 1rem", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: "0.85rem", fontWeight: 500 }}>Slack Connector</span>
              <span style={{ fontSize: "0.75rem", fontWeight: 600, color: slackEnabled ? "var(--success)" : "var(--text-secondary)" }}>
                {slackEnabled ? "● Enabled" : "○ Disabled"}
              </span>
            </div>
          </div>

          <div style={{ borderTop: "1px solid var(--border)", paddingTop: "1.25rem" }}>
            {syncing ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                  <span style={{ color: "var(--accent)", fontWeight: 600, display: "flex", alignItems: "center", gap: "0.5rem" }}>
                    <div style={{ width: "12px", height: "12px", border: "2px solid transparent", borderTopColor: "var(--accent)", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                    {getStageLabel(syncStage)}
                  </span>
                  <span style={{ color: "var(--text-secondary)" }}>{getProgressPercentage(syncStage)}%</span>
                </div>
                
                {/* Progress Bar Container */}
                <div style={{ width: "100%", height: "6px", backgroundColor: "rgba(255,255,255,0.05)", borderRadius: "3px", overflow: "hidden" }}>
                  <div 
                    style={{ 
                      width: `${getProgressPercentage(syncStage)}%`, 
                      height: "100%", 
                      background: "linear-gradient(90deg, var(--accent) 0%, #818cf8 100%)", 
                      borderRadius: "3px",
                      transition: "width 0.4s ease-out",
                      boxShadow: "0 0 8px var(--accent)"
                    }} 
                  />
                </div>
                <style dangerouslySetInnerHTML={{ __html: `@keyframes spin { to { transform: rotate(360deg); } }` }} />
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <button 
                  className="btn btn-primary" 
                  onClick={startSync} 
                  style={{ width: "100%", padding: "0.9rem" }}
                >
                  Sync All Connectors
                </button>

                {syncPagesCreated !== null && (
                  <div style={{ fontSize: "0.85rem", color: "var(--success)", backgroundColor: "rgba(16,185,129,0.05)", border: "1px solid rgba(16,185,129,0.2)", borderRadius: "8px", padding: "0.75rem 1rem", textAlign: "center" }}>
                    ✨ Ingestion successful! Compiled and committed <strong>{syncPagesCreated}</strong> new markdown pages to Git repository.
                  </div>
                )}

                {syncError && (
                  <div style={{ fontSize: "0.85rem", color: "var(--error)", backgroundColor: "rgba(239,68,68,0.05)", border: "1px solid rgba(239,68,68,0.2)", borderRadius: "8px", padding: "0.75rem 1rem", textAlign: "center" }}>
                    ⚠️ {syncError}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Navigation Quick Actions */}
        <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
          <div>
            <h2 style={{ fontSize: "1.35rem", marginBottom: "0.25rem" }}>Portal Destinations</h2>
            <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>Quick navigation shortcuts to review page history and verify changes.</p>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <a 
              href="/inbox" 
              className="btn btn-outline" 
              style={{ textDecoration: "none", textAlign: "center", display: "block" }}
            >
              Open Approval Inbox (Review Drafts)
            </a>
            <a 
              href="/explorer" 
              className="btn btn-outline" 
              style={{ textDecoration: "none", textAlign: "center", display: "block" }}
            >
              Open Explorer (Obsidian Graph & Pages)
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
