import React from "react";

export default function DashboardPage() {
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
            142
          </div>
        </div>
        <div className="card">
          <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", textTransform: "uppercase", marginBottom: "0.5rem" }}>
            Approval Queue Size
          </div>
          <div style={{ fontSize: "2.5rem", fontWeight: 700, fontFamily: "var(--font-display)", color: "var(--warning)" }}>
            3 Pending
          </div>
        </div>
        <div className="card">
          <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", textTransform: "uppercase", marginBottom: "0.5rem" }}>
            Active Synced Sources
          </div>
          <div style={{ fontSize: "2.5rem", fontWeight: 700, fontFamily: "var(--font-display)", color: "var(--accent)" }}>
            2 Sources
          </div>
        </div>
      </div>

      <h2 style={{ fontSize: "1.5rem", marginBottom: "1.5rem" }}>Quick Actions</h2>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1.5rem" }}>
        <div className="card" style={{ cursor: "pointer" }}>
          <h3 style={{ marginBottom: "0.5rem" }}>Review Pending Changes</h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: "1.5rem" }}>
            Approve or reject page modifications compiled from recent Slack threads.
          </p>
          <a href="/inbox" className="btn btn-primary" style={{ textDecoration: "none", display: "inline-block" }}>
            Open Approval Inbox
          </a>
        </div>
        <div className="card" style={{ cursor: "pointer" }}>
          <h3 style={{ marginBottom: "0.5rem" }}>Explore Knowledge Graph</h3>
          <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginBottom: "1.5rem" }}>
            Search, browse, edit sensitivity claims, and inspect version histories.
          </p>
          <a href="/explorer" className="btn btn-outline" style={{ textDecoration: "none", display: "inline-block" }}>
            Open Explorer
          </a>
        </div>
      </div>
    </div>
  );
}
