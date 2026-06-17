"use client";

import React, { useState } from "react";

interface Proposition {
  id: string;
  text: string;
  sensitivity: "public" | "team" | "confidential";
}

interface PageDetail {
  id: string;
  title: string;
  version: number;
  owner: string;
  access_level: string;
  last_updated: string;
  propositions: Proposition[];
  primary_links: string[];
}

const INITIAL_PAGES: PageDetail[] = [
  {
    id: "page_001",
    title: "Standard Shipment Refund Window Policy",
    version: 3,
    owner: "finance_team",
    access_level: "team",
    last_updated: "2026-06-14T09:00:00Z",
    primary_links: ["page_004"],
    propositions: [
      { id: "prop_1", text: "Standard refund requests must be submitted within the 30-day window.", sensitivity: "public" },
      { id: "prop_2", text: "Refunds are processed within 5 business days by finance.", sensitivity: "team" }
    ]
  },
  {
    id: "page_002",
    title: "VIP Exception Discount Processing",
    version: 2,
    owner: "sales_operations",
    access_level: "team",
    last_updated: "2026-06-14T10:15:00Z",
    primary_links: ["page_001"],
    propositions: [
      { id: "prop_1", text: "VIP discount override permits up to 45% discount on enterprise accounts.", sensitivity: "confidential" },
      { id: "prop_2", text: "Sales manager approval is required for all VIP discounts.", sensitivity: "team" }
    ]
  },
  {
    id: "page_004",
    title: "BigQuery Google Data Warehouse Syncing",
    version: 1,
    owner: "data_engineering",
    access_level: "team",
    last_updated: "2026-06-14T11:45:00Z",
    primary_links: [],
    propositions: [
      { id: "prop_1", text: "BigQuery warehouse sync executes automatically on a nightly schedule.", sensitivity: "team" }
    ]
  }
];

export default function ExplorerPage() {
  const [pages, setPages] = useState<PageDetail[]>(INITIAL_PAGES);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState("page_001");

  const filteredPages = pages.filter(p => 
    p.title.toLowerCase().includes(search.toLowerCase()) || 
    p.id.toLowerCase().includes(search.toLowerCase())
  );

  const selectedPage = pages.find(p => p.id === selectedId);

  return (
    <div>
      <h1 className="header-title">Knowledge Explorer</h1>
      <p className="header-subtitle">Search, audit, and inspect sensitivity levels of indexed knowledge pages.</p>

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
                backgroundColor: selectedId === p.id ? "var(--bg-tertiary)" : "var(--bg-secondary)"
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", marginBottom: "0.25rem" }}>
                <span style={{ fontWeight: 600 }}>{p.title}</span>
                <span className="badge badge-approved" style={{ fontSize: "0.65rem", padding: "0.1rem 0.4rem" }}>Active</span>
              </div>
              <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>{p.id} • Owner: {p.owner}</div>
            </div>
          ))}
        </div>

        {/* Selected Page Audit view */}
        {selectedPage && (
          <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
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
                <div style={{ fontWeight: 600, fontSize: "1.1rem" }}>{new Date(selectedPage.last_updated).toLocaleString()}</div>
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

            {/* Claim sensitivity Tagging */}
            <div>
              <h3 style={{ fontSize: "1.1rem", marginBottom: "0.75rem" }}>Propositions & Sensitivity</h3>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)", color: "var(--text-secondary)", textAlign: "left" }}>
                    <th style={{ padding: "0.75rem 0" }}>ID</th>
                    <th style={{ padding: "0.75rem" }}>Claim Sentence</th>
                    <th style={{ padding: "0.75rem 0", textAlign: "right" }}>Sensitivity</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedPage.propositions.map(prop => (
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
            <div>
              <h3 style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>Primary Adjacency Links</h3>
              {selectedPage.primary_links.length === 0 ? (
                <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem" }}>No outbound page links defined.</p>
              ) : (
                <div style={{ display: "flex", gap: "0.5rem" }}>
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
    </div>
  );
}
