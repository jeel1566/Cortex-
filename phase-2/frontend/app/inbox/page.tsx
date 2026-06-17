"use client";

import React, { useState } from "react";

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

const INITIAL_DRAFTS: DraftPage[] = [
  {
    id: "page_007",
    title: "Superset WSGI Worker Configuration",
    last_updated: "2026-06-17T11:00:00Z",
    coverage: 0.96,
    hallucination: 0.00,
    completeness: 9,
    content: `---
id: page_007
title: Superset WSGI Worker Configuration
version: 1
last_updated: 2026-06-17T11:00:00Z
access_level: team
sources:
  - slack://C103/1702890123
propositions:
  - id: prop_1
    text: "The WSGI server for Superset should be Gunicorn running with gevent workers."
    sensitivity: team
---
# Superset WSGI Worker Configuration

When deploying Superset in production, the Gunicorn WSGI server should be configured to use gevent workers rather than thread workers to handle concurrent connection loads efficiently [^1].`,
    sources: [
        "U12345: We should run Gunicorn with gevent workers for Superset to avoid connection pooling issues.",
        "U67890: Agreed, gevent workers handle high thread loads way better."
    ]
  },
  {
    id: "page_008",
    title: "Standard Refund Window Policy",
    last_updated: "2026-06-17T11:15:00Z",
    coverage: 0.92,
    hallucination: 0.02,
    completeness: 8,
    content: `---
id: page_008
title: Standard Refund Window Policy
version: 1
last_updated: 2026-06-17T11:15:00Z
access_level: team
sources:
  - slack://C105/1702890987
propositions:
  - id: prop_1
    text: "Standard refunds must be submitted in under 30 days."
    sensitivity: public
---
# Standard Refund Window Policy

Refunds are processed within 5 business days, provided that requests are submitted within the 30-day window [^1].`,
    sources: [
        "U11111: Remember the refund request window is strictly 30 days.",
        "U22222: Yep, and finance processes them in 5 days."
    ]
  }
];

export default function InboxPage() {
  const [drafts, setDrafts] = useState<DraftPage[]>(INITIAL_DRAFTS);
  const [selectedId, setSelectedId] = useState<string>("page_007");

  const selectedDraft = drafts.find(d => d.id === selectedId);

  const handleApprove = (id: string) => {
    alert(`Page ${id} approved successfully!`);
    setDrafts(drafts.filter(d => d.id !== id));
    // Auto-select another if available
    const remaining = drafts.filter(d => d.id !== id);
    if (remaining.length > 0) {
      setSelectedId(remaining[0].id);
    }
  };

  const handleReject = (id: string) => {
    alert(`Page ${id} rejected.`);
    setDrafts(drafts.filter(d => d.id !== id));
    const remaining = drafts.filter(d => d.id !== id);
    if (remaining.length > 0) {
      setSelectedId(remaining[0].id);
    }
  };

  return (
    <div>
      <h1 className="header-title">Approval Inbox</h1>
      <p className="header-subtitle">Review and validate newly synthesized corporate knowledge drafts.</p>

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
                  borderColor: selectedId === draft.id ? "var(--accent)" : "var(--border)",
                  backgroundColor: selectedId === draft.id ? "var(--bg-tertiary)" : "var(--bg-secondary)"
                }}
              >
                <div style={{ fontWeight: 600, marginBottom: "0.25rem" }}>{draft.title}</div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>{draft.id} • Validation Score: {draft.completeness}/10</div>
              </div>
            ))}
          </div>

          {/* Details & Review Panel */}
          {selectedDraft && (
            <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid var(--border)", paddingBottom: "1rem" }}>
                <div>
                  <h2 style={{ fontSize: "1.5rem" }}>{selectedDraft.title}</h2>
                  <span className="badge badge-draft" style={{ marginTop: "0.5rem", display: "inline-block" }}>Awaiting Review</span>
                </div>
                <div style={{ display: "flex", gap: "0.75rem" }}>
                  <button className="btn btn-outline" style={{ color: "var(--error)", borderColor: "rgba(239, 68, 68, 0.3)" }} onClick={() => handleReject(selectedDraft.id)}>
                    Reject
                  </button>
                  <button className="btn btn-primary" onClick={() => handleApprove(selectedDraft.id)}>
                    Approve & Index
                  </button>
                </div>
              </div>

              {/* Validation Summary */}
              <div>
                <h3 style={{ fontSize: "1.1rem", marginBottom: "0.75rem" }}>Quality Validation Scores</h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem" }}>
                  <div style={{ padding: "0.75rem", borderRadius: "6px", border: "1px solid var(--border)", backgroundColor: "rgba(255,255,255,0.02)" }}>
                    <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Proposition Coverage</div>
                    <div style={{ fontSize: "1.2rem", fontWeight: 600, color: "var(--success)" }}>{(selectedDraft.coverage * 100).toFixed(0)}%</div>
                  </div>
                  <div style={{ padding: "0.75rem", borderRadius: "6px", border: "1px solid var(--border)", backgroundColor: "rgba(255,255,255,0.02)" }}>
                    <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Hallucination Rate</div>
                    <div style={{ fontSize: "1.2rem", fontWeight: 600, color: selectedDraft.hallucination <= 0.02 ? "var(--success)" : "var(--error)" }}>{(selectedDraft.hallucination * 100).toFixed(0)}%</div>
                  </div>
                  <div style={{ padding: "0.75rem", borderRadius: "6px", border: "1px solid var(--border)", backgroundColor: "rgba(255,255,255,0.02)" }}>
                    <div style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Completeness Score</div>
                    <div style={{ fontSize: "1.2rem", fontWeight: 600, color: "var(--warning)" }}>{selectedDraft.completeness}/10</div>
                  </div>
                </div>
              </div>

              {/* Document Code Preview */}
              <div>
                <h3 style={{ fontSize: "1.1rem", marginBottom: "0.75rem" }}>Proposed Markdown Code</h3>
                <pre style={{ backgroundColor: "#000", padding: "1rem", borderRadius: "6px", border: "1px solid var(--border)", overflowX: "auto", fontFamily: "monospace", fontSize: "0.9rem", color: "var(--text-secondary)" }}>
                  {selectedDraft.content}
                </pre>
              </div>

              {/* Traceable Sources */}
              <div>
                <h3 style={{ fontSize: "1.1rem", marginBottom: "0.75rem" }}>Source Logs (Slack Conversation)</h3>
                <ul style={{ display: "flex", flexDirection: "column", gap: "0.5rem", listStyle: "none" }}>
                  {selectedDraft.sources.map((src, i) => (
                    <li key={i} style={{ padding: "0.75rem", borderRadius: "6px", backgroundColor: "rgba(255,255,255,0.01)", borderLeft: "3px solid var(--accent)", fontSize: "0.9rem" }}>
                      {src}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
