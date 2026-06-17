"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";

interface Proposition {
  id: string;
  text: string;
  sensitivity: "public" | "team" | "confidential";
}

interface PageSummary {
  id: string;
  title: string;
  version: number;
  owner: string;
  access_level: string;
  last_updated: string;
}

interface PageDetail extends PageSummary {
  content: string;
  propositions: Proposition[];
  primary_links: string[];
}

export default function ExplorerPage() {
  const { getToken } = useAuth();
  const [pages, setPages] = useState<PageSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [selectedPage, setSelectedPage] = useState<PageDetail | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  // Fetch all page summaries on mount
  useEffect(() => {
    const fetchPages = async () => {
      setLoading(true);
      try {
        const token = await getAuthToken();
        const res = await fetch("http://127.0.0.1:8000/v1/pages", {
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });
        if (!res.ok) {
          throw new Error(`Server returned ${res.status}: ${res.statusText}`);
        }
        const data = await res.json();
        setPages(data);
        if (data.length > 0) {
          setSelectedId(data[0].id);
        }
      } catch (err: any) {
        setError(err.message || "Failed to load pages from server");
      } finally {
        setLoading(false);
      }
    };

    fetchPages();
  }, []);

  // Fetch page details when selectedId changes
  useEffect(() => {
    if (!selectedId) return;

    const fetchPageDetail = async () => {
      setLoadingDetail(true);
      try {
        const token = await getAuthToken();
        const res = await fetch(`http://127.0.0.1:8000/v1/page/${selectedId}`, {
          headers: {
            "Authorization": `Bearer ${token}`
          }
        });
        if (!res.ok) {
          throw new Error(`Failed to load page details: ${res.statusText}`);
        }
        const data = await res.json();
        setSelectedPage(data);
      } catch (err: any) {
        console.error(err);
      } finally {
        setLoadingDetail(false);
      }
    };

    fetchPageDetail();
  }, [selectedId]);

  const filteredPages = pages.filter(p => 
    p.title.toLowerCase().includes(search.toLowerCase()) || 
    p.id.toLowerCase().includes(search.toLowerCase())
  );

  if (loading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "50vh", color: "var(--text-secondary)" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: "1.2rem", fontWeight: 600, marginBottom: "0.5rem" }}>Loading Knowledge Explorer...</div>
          <div style={{ fontSize: "0.9rem", color: "var(--text-muted)" }}>Fetching index files from tenant repository</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "2rem" }}>
        <h1 className="header-title" style={{ color: "var(--error)" }}>Connection Error</h1>
        <div className="card" style={{ marginTop: "1rem", borderColor: "var(--error)" }}>
          <p style={{ marginBottom: "1rem" }}>Could not connect to the Cortex Backend service.</p>
          <code style={{ display: "block", backgroundColor: "rgba(0,0,0,0.2)", padding: "1rem", borderRadius: "6px", fontSize: "0.85rem", color: "var(--warning)" }}>
            {error}
          </code>
          <button className="btn btn-primary" style={{ marginTop: "1.5rem" }} onClick={() => window.location.reload()}>
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      <h1 className="header-title">Knowledge Explorer</h1>
      <p className="header-subtitle">Search, audit, and inspect sensitivity levels of indexed knowledge pages.</p>

      {pages.length === 0 ? (
        <div className="card" style={{ textAlign: "center", padding: "4rem 1rem", marginTop: "2rem" }}>
          <h3 style={{ marginBottom: "0.5rem", fontSize: "1.25rem" }}>No Pages Indexed</h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", maxWidth: "500px", margin: "0 auto 1.5rem" }}>
            The tenant repository is currently empty. Run an ingestion job or connect Notion/Slack channels to compile your first page.
          </p>
        </div>
      ) : (
        <>
          {/* Search Input */}
          <div style={{ marginBottom: "2rem" }}>
            <input 
              type="text" 
              placeholder="Search by title, keywords, or page ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ 
                width: "100%", 
                padding: "1rem", 
                backgroundColor: "var(--bg-secondary)", 
                border: "1px solid var(--border)", 
                borderRadius: "8px", 
                color: "#fff",
                fontSize: "1rem",
                outline: "none"
              }}
            />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", gap: "2rem", alignItems: "start" }}>
            {/* Pages List */}
            <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              {filteredPages.map(p => (
                <div 
                  key={p.id} 
                  onClick={() => setSelectedId(p.id)}
                  className="card" 
                  style={{ 
                    cursor: "pointer", 
                    borderColor: selectedId === p.id ? "var(--accent)" : "var(--border)",
                    backgroundColor: selectedId === p.id ? "var(--bg-tertiary)" : "var(--bg-secondary)",
                    transition: "all 0.2s ease"
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", marginBottom: "0.25rem" }}>
                    <span style={{ fontWeight: 600 }}>{p.title}</span>
                    <span className="badge badge-approved" style={{ fontSize: "0.65rem", padding: "0.1rem 0.4rem" }}>Active</span>
                  </div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>{p.id} • Owner: {p.owner}</div>
                </div>
              ))}
              {filteredPages.length === 0 && (
                <div style={{ color: "var(--text-secondary)", fontSize: "0.9rem", textAlign: "center", padding: "2rem" }}>
                  No pages match your search.
                </div>
              )}
            </div>

            {/* Selected Page Audit view */}
            {selectedPage && (
              <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem", opacity: loadingDetail ? 0.6 : 1, transition: "opacity 0.15s ease" }}>
                <div style={{ borderBottom: "1px solid var(--border)", paddingBottom: "1rem" }}>
                  <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>{selectedPage.id}</div>
                  <h2 style={{ fontSize: "1.75rem", marginTop: "0.25rem" }}>{selectedPage.title}</h2>
                </div>

                {/* Metadata Fields */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "1.5rem" }}>
                  <div>
                    <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Revision Version</span>
                    <div style={{ fontWeight: 600, fontSize: "1.1rem" }}>v{selectedPage.version}</div>
                  </div>
                  <div>
                    <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Last Updated</span>
                    <div style={{ fontWeight: 600, fontSize: "1.1rem" }}>
                      {selectedPage.last_updated ? new Date(selectedPage.last_updated).toLocaleString() : "Never"}
                    </div>
                  </div>
                  <div>
                    <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Owner Group</span>
                    <div style={{ fontWeight: 600, fontSize: "1.1rem" }}>{selectedPage.owner}</div>
                  </div>
                  <div>
                    <span style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>Access Level</span>
                    <div style={{ fontWeight: 600, fontSize: "1.1rem", textTransform: "capitalize" }}>{selectedPage.access_level}</div>
                  </div>
                </div>

                {/* Page Content View */}
                <div style={{ borderTop: "1px solid var(--border)", paddingTop: "1.5rem" }}>
                  <h3 style={{ fontSize: "1.1rem", marginBottom: "0.75rem" }}>Page Content</h3>
                  <div 
                    style={{ 
                      whiteSpace: "pre-wrap", 
                      fontFamily: "var(--font-mono, monospace)", 
                      fontSize: "0.9rem", 
                      backgroundColor: "rgba(0,0,0,0.15)", 
                      padding: "1rem", 
                      borderRadius: "6px",
                      border: "1px solid rgba(255,255,255,0.05)",
                      lineHeight: "1.6",
                      color: "#e2e8f0"
                    }}
                  >
                    {selectedPage.content}
                  </div>
                </div>

                {/* Claim sensitivity Tagging */}
                <div style={{ borderTop: "1px solid var(--border)", paddingTop: "1.5rem" }}>
                  <h3 style={{ fontSize: "1.1rem", marginBottom: "0.75rem" }}>Propositions & Sensitivity Clearance</h3>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                    <thead>
                      <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--text-secondary)", textAlign: "left" }}>
                        <th style={{ padding: "0.75rem 0" }}>ID</th>
                        <th style={{ padding: "0.75rem" }}>Claim Sentence</th>
                        <th style={{ padding: "0.75rem 0", textAlign: "right" }}>Sensitivity</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedPage.propositions && selectedPage.propositions.map(prop => (
                        <tr key={prop.id} style={{ borderBottom: "1px solid rgba(255,255,255,0.03)" }}>
                          <td style={{ padding: "0.75rem 0", color: "var(--accent)", fontWeight: 600 }}>{prop.id}</td>
                          <td style={{ padding: "0.75rem" }}>{prop.text}</td>
                          <td style={{ padding: "0.75rem 0", textAlign: "right" }}>
                            <span 
                              className="badge"
                              style={{
                                backgroundColor: prop.sensitivity === "public" ? "rgba(16,185,129,0.15)" : prop.sensitivity === "team" ? "rgba(99,102,241,0.15)" : "rgba(239,68,68,0.15)",
                                color: prop.sensitivity === "public" ? "var(--success)" : prop.sensitivity === "team" ? "var(--accent)" : "var(--error)",
                                border: prop.sensitivity === "public" ? "1px solid rgba(16,185,129,0.3)" : prop.sensitivity === "team" ? "1px solid rgba(99,102,241,0.3)" : "1px solid rgba(239,68,68,0.3)",
                              }}
                            >
                              {prop.sensitivity}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Adjacency links */}
                <div style={{ borderTop: "1px solid var(--border)", paddingTop: "1.5rem" }}>
                  <h3 style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>Primary Adjacency Links</h3>
                  {!selectedPage.primary_links || selectedPage.primary_links.length === 0 ? (
                    <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>No outbound page links defined.</p>
                  ) : (
                    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                      {selectedPage.primary_links.map(link => (
                        <span 
                          key={link}
                          onClick={() => setSelectedId(link)}
                          style={{ 
                            padding: "0.5rem 0.75rem", 
                            borderRadius: "6px", 
                            backgroundColor: "var(--bg-tertiary)", 
                            border: "1px solid var(--border)", 
                            cursor: "pointer", 
                            fontSize: "0.85rem",
                            color: "var(--accent)"
                          }}
                        >
                          {link}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
