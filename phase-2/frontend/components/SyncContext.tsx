"use client";

import React, { createContext, useContext, useState, useEffect, useRef } from "react";
import { useAuth } from "@clerk/nextjs";

interface SyncContextType {
  syncing: boolean;
  syncJobId: string;
  syncStage: string;
  syncStatus: string;
  syncPagesCreated: number | null;
  syncError: string | null;
  startSync: () => Promise<void>;
  fetchDashboardMetrics?: () => Promise<void>;
}

const SyncContext = createContext<SyncContextType | undefined>(undefined);

export function SyncProvider({ children }: { children: React.ReactNode }) {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  
  const [syncing, setSyncing] = useState(false);
  const [syncJobId, setSyncJobId] = useState("");
  const [syncStage, setSyncStage] = useState("");
  const [syncStatus, setSyncStatus] = useState("");
  const [syncPagesCreated, setSyncPagesCreated] = useState<number | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);

  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

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

  const getStageLabel = (stage: string) => {
    const stages: Record<string, string> = {
      "initiating": "Initiating connection...",
      "queued": "Awaiting resource queue...",
      "fetching_sources": "Scanning enabled connectors...",
      "notion_fetch": "Fetching documents from Notion...",
      "slack_fetch": "Retrieving Slack channel threads...",
      "sample_sync": "Ingesting fallback demo metadata...",
      "pii_redaction": "Redacting PII and filtering logs...",
      "sentence_splitting": "Decomposing block text...",
      "speech_act_classification": "Running speech act classification...",
      "sentence_clustering": "Clustering propositions...",
      "page_synthesis": "Synthesizing Markdown pages...",
      "graph_indexing": "Mapping Knowledge Graph...",
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

  const pollJobStatus = async (jobId: string) => {
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
    }

    const runPoll = async () => {
      try {
        const token = await getAuthToken();
        const res = await fetch(`http://127.0.0.1:8000/v1/ingest/${jobId}`, {
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          setSyncStatus(data.status);
          setSyncStage(data.current_stage || data.status);

          if (data.status === "complete") {
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
            setSyncing(false);
            setSyncPagesCreated(data.pages_created);
            // Refresh main window dashboard count if custom event is listened to
            window.dispatchEvent(new CustomEvent("cortex-sync-completed"));
          } else if (data.status === "failed") {
            if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
            setSyncing(false);
            setSyncError("Pipeline execution failed. Please verify credentials in Settings.");
          }
        } else if (res.status === 401) {
          // Token expired, let's log but keep polling (token will refresh next interval)
          console.warn("Clerk token expired during polling. Will refresh on next attempt.");
        }
      } catch (e) {
        console.error("Polling error:", e);
      }
    };

    // Run first check immediately
    await runPoll();

    // Start interval
    pollIntervalRef.current = setInterval(runPoll, 1500);
  };

  // Check on mount for any active/stale jobs running
  useEffect(() => {
    const recoverActiveSync = async () => {
      try {
        const token = await getAuthToken();
        const res = await fetch("http://127.0.0.1:8000/v1/ingest/latest", {
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          if (data.job_id && (data.status === "processing" || data.status === "queued")) {
            setSyncJobId(data.job_id);
            setSyncing(true);
            setSyncStatus(data.status);
            setSyncStage(data.current_stage || data.status);
            pollJobStatus(data.job_id);
          }
        }
      } catch (e) {
        console.error("Error checking active sync status:", e);
      }
    };

    if (isLoaded) {
      recoverActiveSync();
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, [isLoaded, isSignedIn]);

  const startSync = async () => {
    setSyncing(true);
    setSyncError(null);
    setSyncPagesCreated(null);
    setSyncStage("initiating");
    setSyncStatus("queued");

    try {
      const token = await getAuthToken();
      const res = await fetch("http://127.0.0.1:8000/v1/sync/all", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "Content-Type": "application/json"
        }
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || "Failed to trigger sync pipeline");
      }

      const data = await res.json();
      const jobId = data.job_id;
      setSyncJobId(jobId);
      pollJobStatus(jobId);
    } catch (err: any) {
      setSyncing(false);
      setSyncError(err.message || "Failed to initiate ingestion sync.");
    }
  };

  return (
    <SyncContext.Provider value={{ syncing, syncJobId, syncStage, syncStatus, syncPagesCreated, syncError, startSync }}>
      {children}
      
      {/* Floating Global Progress Tracker Card (Bottom Right) */}
      {syncing && (
        <div style={{
          position: "fixed",
          bottom: "24px",
          right: "24px",
          width: "360px",
          background: "rgba(18, 18, 24, 0.95)",
          backdropFilter: "blur(12px)",
          border: "1px solid var(--border)",
          borderRadius: "12px",
          padding: "1.25rem",
          boxShadow: "0 10px 30px rgba(0, 0, 0, 0.5)",
          zIndex: 9999,
          display: "flex",
          flexDirection: "column",
          gap: "0.75rem",
          fontFamily: "sans-serif"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: "0.9rem", fontWeight: 600, color: "#fff", display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span style={{
                display: "inline-block",
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                backgroundColor: "var(--accent)",
                animation: "pulse 1.5s infinite"
              }}></span>
              Ingestion Pipeline Active
            </span>
            <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
              {getProgressPercentage(syncStage)}%
            </span>
          </div>

          <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)", minHeight: "1.2rem" }}>
            {getStageLabel(syncStage)}
          </div>

          {/* Progress bar container */}
          <div style={{ width: "100%", height: "4px", backgroundColor: "rgba(255,255,255,0.05)", borderRadius: "2px", overflow: "hidden" }}>
            <div style={{
              width: `${getProgressPercentage(syncStage)}%`,
              height: "100%",
              backgroundColor: "var(--accent)",
              borderRadius: "2px",
              transition: "width 0.4s cubic-bezier(0.4, 0, 0.2, 1)"
            }}></div>
          </div>
          
          <style dangerouslySetInnerHTML={{ __html: `
            @keyframes pulse {
              0% { transform: scale(0.9); opacity: 0.5; }
              50% { transform: scale(1.2); opacity: 1; }
              100% { transform: scale(0.9); opacity: 0.5; }
            }
          `}} />
        </div>
      )}
    </SyncContext.Provider>
  );
}

export function useSync() {
  const context = useContext(SyncContext);
  if (context === undefined) {
    throw new Error("useSync must be used within a SyncProvider");
  }
  return context;
}
