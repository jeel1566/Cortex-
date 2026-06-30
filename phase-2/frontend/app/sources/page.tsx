"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";

interface SourceObject {
  id: string;
  connector_type: string;
  external_id: string;
  object_type: string;
  title: string;
  url: string;
  author: string;
  created_at: string;
  updated_at: string;
  content_hash: string;
}

export default function SourcesPage() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [sources, setSources] = useState<SourceObject[]>([]);
  const [loading, setLoading] = useState(true);
  
  // Uploading states
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

  const fetchSources = async () => {
    try {
      const token = await getAuthToken();
      const res = await fetch("http://127.0.0.1:8000/v1/source-objects", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSources(data);
      }
    } catch (e) {
      console.error("Error fetching sources:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSources();
  }, [isLoaded, isSignedIn]);

  const pollSyncJob = async (jobId: string, token: string) => {
    const intervalId = setInterval(async () => {
      try {
        const res = await fetch(`http://127.0.0.1:8000/v1/sync-runs/${jobId}`, {
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          const status = data.status;
          
          if (status === "completed") {
            setUploadStatus("done");
            const counts = data.counts || {};
            setUploadMessage(`✓ File uploaded and compiled! Ingested ${counts.objects || 0} objects, created ${counts.drafts || 0} drafts.`);
            clearInterval(intervalId);
            fetchSources();
            setTimeout(() => {
              setUploadStatus("idle");
              setUploadMessage("");
            }, 8000);
          } else if (status === "failed") {
            setUploadStatus("error");
            setUploadMessage(`Processing failed: ${data.error_message || "Unknown error"}`);
            clearInterval(intervalId);
          } else {
            setUploadMessage("Ingestion worker is processing and validation compiling document...");
          }
        }
      } catch (e) {
        console.error("Error polling sync run:", e);
      }
    }, 1500);
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
        pollSyncJob(data.job_id, token);
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

  return (
    <div>
      <h1 className="header-title">Sources Explorer</h1>
      <p className="header-subtitle">Upload local corporate documents and track active synced workspace objects.</p>

      {/* Upload Zone */}
      <div className="card" style={{ marginBottom: "3rem" }}>
        <h2 style={{ fontSize: "1.35rem", marginBottom: "0.5rem" }}>Local Document Drop</h2>
        <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginBottom: "1.5rem" }}>
          Drop or select a file to instantly segment and index it into the Knowledge OS store.
        </p>

        <div style={{
          border: "2px dashed var(--border)",
          borderRadius: "12px",
          padding: "3.5rem 2rem",
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
          <div style={{ fontWeight: 600, fontSize: "1.1rem", marginBottom: "0.25rem" }}>Drag & Drop or Click to Upload Document</div>
          <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Supports Markdown (.md), PDF, TXT, Word DOCX, Excel, CSV</div>
        </div>

        {uploadMessage && (
          <div style={{
            marginTop: "1.5rem",
            padding: "1rem",
            borderRadius: "8px",
            fontSize: "0.85rem",
            background: uploadStatus === "done" ? "rgba(99, 168, 124, 0.1)" : uploadStatus === "error" ? "rgba(207, 102, 102, 0.1)" : "rgba(255,255,255,0.03)",
            border: `1px solid ${uploadStatus === "done" ? "rgba(99, 168, 124, 0.2)" : uploadStatus === "error" ? "rgba(207, 102, 102, 0.2)" : "var(--border)"}`,
            color: uploadStatus === "done" ? "var(--success)" : uploadStatus === "error" ? "var(--error)" : "var(--text-primary)"
          }}>
            {uploadMessage}
          </div>
        )}
      </div>

      {/* Sources list */}
      <div className="card">
        <h2 style={{ fontSize: "1.35rem", marginBottom: "1rem" }}>Ingested Source Registry</h2>
        
        {loading ? (
          <div style={{ color: "var(--text-secondary)", fontSize: "0.85rem", padding: "1.5rem", textAlign: "center" }}>
            Loading sources...
          </div>
        ) : sources.length === 0 ? (
          <div style={{ padding: "2rem", textAlign: "center", border: "1px dashed var(--border)", borderRadius: "8px", color: "var(--text-secondary)", fontSize: "0.85rem" }}>
            ℹ️ No sources ingested yet. Upload a local document or sync active connectors.
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.85rem", textAlign: "left" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--text-secondary)" }}>
                  <th style={{ padding: "0.75rem 0.5rem" }}>Title</th>
                  <th style={{ padding: "0.75rem 0.5rem" }}>Connector</th>
                  <th style={{ padding: "0.75rem 0.5rem" }}>Type</th>
                  <th style={{ padding: "0.75rem 0.5rem" }}>Added At</th>
                  <th style={{ padding: "0.75rem 0.5rem", textAlign: "right" }}>External ID</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((src) => (
                  <tr key={src.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                    <td style={{ padding: "0.75rem 0.5rem", fontWeight: 600, color: "#fff" }}>
                      {src.title}
                    </td>
                    <td style={{ padding: "0.75rem 0.5rem", textTransform: "capitalize", color: "var(--accent)" }}>
                      {src.connector_type}
                    </td>
                    <td style={{ padding: "0.75rem 0.5rem", textTransform: "capitalize" }}>
                      {src.object_type}
                    </td>
                    <td style={{ padding: "0.75rem 0.5rem", color: "var(--text-secondary)" }}>
                      {new Date(src.created_at).toLocaleString()}
                    </td>
                    <td style={{ padding: "0.75rem 0.5rem", textAlign: "right", fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "var(--text-secondary)" }}>
                      {src.external_id}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
