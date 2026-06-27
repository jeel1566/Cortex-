"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@clerk/nextjs";

export default function DashboardPage() {
  const { getToken, isLoaded, isSignedIn } = useAuth();
  const [loading, setLoading] = useState(true);
  const [pagesCount, setPagesCount] = useState(0);
  const [activeSources, setActiveSources] = useState(0);

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

  useEffect(() => {
    const fetchDashboardMetrics = async () => {
      setLoading(true);
      try {
        const token = await getAuthToken();
        
        // 1. Fetch total pages count
        const pagesRes = await fetch("http://127.0.0.1:8000/v1/pages", {
          headers: { "Authorization": `Bearer ${token}` }
        });
        let pagesCountVal = 0;
        if (pagesRes.ok) {
          const pagesData = await pagesRes.json();
          // Filter out README since it's just a placeholder repository page
          const realPages = pagesData.filter((p: any) => p.id !== "README");
          pagesCountVal = realPages.length;
          setPagesCount(pagesCountVal);
        }

        // 2. Fetch settings to determine active sync sources
        const settingsRes = await fetch("http://127.0.0.1:8000/v1/settings", {
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (settingsRes.ok) {
          const settingsData = await settingsRes.json();
          let sourcesCount = 0;
          if (settingsData.connectors) {
            if (settingsData.connectors.notion?.enabled) sourcesCount += 1;
            if (settingsData.connectors.slack?.enabled) sourcesCount += 1;
          }
          setActiveSources(sourcesCount);
        }
      } catch (e) {
        console.error("Error loading dashboard metrics:", e);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardMetrics();
  }, [isLoaded, isSignedIn]);

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
