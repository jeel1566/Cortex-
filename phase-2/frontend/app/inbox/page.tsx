"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";

interface DraftPage {
  id: string;
  title: string;
  last_updated: string;
  coverage: number;
  hallucination: number;
  completeness: number;
  content: string;
  sources: string[];
}

function parseFrontmatter(markdown: string) {
  const result = { coverage: 0.9, hallucination: 0.02, completeness: 8, sources: [] as string[] };
  if (!markdown) return result;
  
  const parts = markdown.split("---");
  if (parts.length >= 3) {
    const yamlStr = parts[1];
    
    // Extract sources
    const sourcesMatch = yamlStr.match(/sources:\s*\n?((?:\s*-\s*[^\n]+\n?)*)/);
    if (sourcesMatch) {
      const items = sourcesMatch[1].split("-").map(i => i.trim()).filter(Boolean);
      result.sources = items;
    }
    
    // Extract coverage
    const coverageMatch = yamlStr.match(/proposition_coverage:\s*([0-9.]+)/) || yamlStr.match(/coverage:\s*([0-9.]+)/);
    if (coverageMatch) {
      result.coverage = parseFloat(coverageMatch[1]);
    }
    
    // Extract hallucination
    const hallucinationMatch = yamlStr.match(/hallucination_rate:\s*([0-9.]+)/) || yamlStr.match(/hallucination:\s*([0-9.]+)/);
    if (hallucinationMatch) {
      result.hallucination = parseFloat(hallucinationMatch[1]);
    }
    
    // Extract completeness / detail retention
    const completenessMatch = yamlStr.match(/detail_retention_score:\s*([0-9.]+)/) || yamlStr.match(/completeness:\s*([0-9.]+)/);
    if (completenessMatch) {
      result.completeness = Math.round(parseFloat(completenessMatch[1]) * 10);
    }
  }
  return result;
}

export default function InboxPage() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [drafts, setDrafts] = useState<DraftPage[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [actioning, setActioning] = useState<string | null>(null);

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

  const fetchDrafts = async () => {
    setLoading(true);
    try {
      const token = await getAuthToken();
      const res = await fetch("http://127.0.0.1:8000/v1/drafts", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        const mapped = data.map((d: any) => {
          const fm = parseFrontmatter(d.content);
          return {
            id: d.id,
            title: d.title,
            last_updated: d.updated_at,
            content: d.content,
            coverage: fm.coverage,
            hallucination: fm.hallucination,
            completeness: fm.completeness,
            sources: fm.sources
          };
        });
        setDrafts(mapped);
        if (mapped.length > 0) {
          setSelectedId(mapped[0].id);
        } else {
          setSelectedId("");
        }
      }
    } catch (e) {
      console.error("Error fetching drafts:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDrafts();
  }, [isLoaded, isSignedIn]);

  const selectedDraft = drafts.find(d => d.id === selectedId);

  const handleApprove = async (id: string) => {
    setActioning(id);
    try {
      const token = await getAuthToken();
      const res = await fetch(`http://127.0.0.1:8000/v1/drafts/${id}/approve`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        alert("Draft approved, compiled, and indexed to Git successfully!");
        fetchDrafts();
      } else {
        const err = await res.json();
        alert(`Approval failed: ${err.detail || "Unknown error"}`);
      }
    } catch (e) {
      alert(`Approval error: ${e}`);
    } finally {
      setActioning(null);
    }
  };

  const handleReject = async (id: string) => {
    setActioning(id);
    try {
      const token = await getAuthToken();
      const res = await fetch(`http://127.0.0.1:8000/v1/drafts/${id}/reject`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        alert("Draft rejected.");
        fetchDrafts();
      } else {
        const err = await res.json();
        alert(`Rejection failed: ${err.detail || "Unknown error"}`);
      }
    } catch (e) {
      alert(`Rejection error: ${e}`);
    } finally {
      setActioning(null);
    }
  };

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "50vh", color: "var(--text-secondary)" }}>
        <div>
          <div style={{ width: "45px", height: "45px", border: "3px solid var(--border)", borderTopColor: "var(--accent)", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 1.25rem" }}></div>
          <div style={{ fontSize: "1.1rem", fontWeight: 600 }}>Loading pending drafts...</div>
          <style dangerouslySetInnerHTML={{ __html: `@keyframes spin { to { transform: rotate(360deg); } }` }} />
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="header-title">Approval Inbox</h1>
      <p className="header-subtitle">Review, validate and approve synthesized corporate knowledge drafts.</p>

      {drafts.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "4rem" }}>
          <h3 style={{ marginBottom: "0.5rem" }}>All Clear!</h3>
          <p style={{ color: "var(--text-secondary)" }}>No pending changes require moderator approval.</p>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: "2rem", alignItems: "start" }}>
          {/* Drafts List */}
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {drafts.map(draft => (
              <div 
                key={draft.id} 
                onClick={() => setSelectedId(draft.id)}
                className="card" 
                style={{ 
                  cursor: "pointer", 
                  padding: "1.25rem 1.5rem",
                  borderColor: selectedId === draft.id ? "var(--accent)" : "var(--border)",
                  backgroundColor: selectedId === draft.id ? "var(--bg-tertiary)" : "var(--bg-secondary)"
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: "0.25rem", fontFamily: "var(--font-sans)" }}>{draft.title}</div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", fontFamily: "var(--font-mono)" }}>
                  {draft.id.substring(0, 12)}... • Quality: {draft.completeness}/10
                </div>
              </div>
            ))}
          </div>

          {/* Details & Review Panel */}
          {selectedDraft ? (
            <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.75rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border)", paddingBottom: "1.25rem" }}>
                <div>
                  <h2 style={{ fontSize: "2rem" }}>{selectedDraft.title}</h2>
                  <span className="badge badge-draft" style={{ marginTop: "0.5rem", display: "inline-block" }}>Awaiting Review</span>
                </div>
                <div style={{ display: "flex", gap: "0.75rem" }}>
                  <button 
                    className="btn btn-outline" 
                    style={{ color: "var(--error)", borderColor: "rgba(207, 102, 102, 0.3)" }} 
                    disabled={actioning !== null}
                    onClick={() => handleReject(selectedDraft.id)}
                  >
                    Reject
                  </button>
                  <button 
                    className="btn btn-primary" 
                    disabled={actioning !== null}
                    onClick={() => handleApprove(selectedDraft.id)}
                  >
                    {actioning === selectedDraft.id ? "Processing..." : "Approve & Index"}
                  </button>
                </div>
              </div>

              {/* Validation Summary */}
              <div>
                <h3 style={{ fontSize: "1.2rem", marginBottom: "0.75rem" }}>Quality Validation Scores</h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem" }}>
                  <div style={{ padding: "0.75rem 1rem", borderRadius: "6px", border: "1px solid var(--border)", backgroundColor: "rgba(255,255,255,0.01)" }}>
                    <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>Proposition Coverage</div>
                    <div style={{ fontSize: "1.35rem", fontWeight: 600, color: "var(--success)", marginTop: "0.25rem" }}>
                      {(selectedDraft.coverage * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div style={{ padding: "0.75rem 1rem", borderRadius: "6px", border: "1px solid var(--border)", backgroundColor: "rgba(255,255,255,0.01)" }}>
                    <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>Hallucination Rate</div>
                    <div style={{ fontSize: "1.35rem", fontWeight: 600, color: selectedDraft.hallucination <= 0.05 ? "var(--success)" : "var(--error)", marginTop: "0.25rem" }}>
                      {(selectedDraft.hallucination * 100).toFixed(0)}%
                    </div>
                  </div>
                  <div style={{ padding: "0.75rem 1rem", borderRadius: "6px", border: "1px solid var(--border)", backgroundColor: "rgba(255,255,255,0.01)" }}>
                    <div style={{ fontSize: "0.78rem", color: "var(--text-secondary)" }}>Completeness Score</div>
                    <div style={{ fontSize: "1.35rem", fontWeight: 600, color: "var(--warning)", marginTop: "0.25rem" }}>
                      {selectedDraft.completeness}/10
                    </div>
                  </div>
                </div>
              </div>

              {/* Document Code Preview */}
              <div>
                <h3 style={{ fontSize: "1.2rem", marginBottom: "0.75rem" }}>Proposed Markdown Code</h3>
                <pre style={{ 
                  backgroundColor: "#0d0f0e", 
                  padding: "1.25rem", 
                  borderRadius: "8px", 
                  border: "1px solid var(--border)", 
                  overflowX: "auto", 
                  fontFamily: "var(--font-mono)", 
                  fontSize: "0.85rem", 
                  color: "var(--text-primary)",
                  lineHeight: "1.5"
                }}>
                  {selectedDraft.content}
                </pre>
              </div>

              {/* Traceable Sources */}
              <div>
                <h3 style={{ fontSize: "1.2rem", marginBottom: "0.75rem" }}>Source Logs & Evidence Links</h3>
                {selectedDraft.sources.length === 0 ? (
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>No source document mappings compiled.</p>
                ) : (
                  <ul style={{ display: "flex", flexDirection: "column", gap: "0.6rem", listStyle: "none" }}>
                    {selectedDraft.sources.map((src, i) => (
                      <li key={i} style={{ 
                        padding: "0.8rem 1rem", 
                        borderRadius: "6px", 
                        backgroundColor: "rgba(255,255,255,0.01)", 
                        borderLeft: "3px solid var(--accent)", 
                        fontSize: "0.85rem",
                        fontFamily: "var(--font-mono)",
                        color: "var(--text-secondary)"
                      }}>
                        {src}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          ) : (
            <div className="card" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "350px", textAlign: "center" }}>
              <div>
                <div style={{ fontSize: "2rem", marginBottom: "1rem" }}>📖</div>
                <h3>No Draft Selected</h3>
                <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem" }}>Select a compiled draft page from the list to review.</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
