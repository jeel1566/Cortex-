import { ClerkProvider, SignedIn, SignedOut, SignIn, UserButton } from "@clerk/nextjs";
import MainAppWrapper from "../components/MainAppWrapper";
import "./globals.css";
import React from "react";

export const metadata = {
  title: "Cortex Admin Portal",
  description: "Management dashboard for Cortex corporate Knowledge OS",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <ClerkProvider>
          {/* Centered Premium Login Screen if Signed Out */}
          <SignedOut>
            <div style={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center", background: "#09090b" }}>
              <div style={{ width: "100%", maxWidth: "440px", padding: "2.5rem", background: "var(--bg-secondary)", borderRadius: "16px", border: "1px solid var(--border)", boxShadow: "0 20px 50px rgba(0,0,0,0.6)" }}>
                <div style={{ textAlign: "center", marginBottom: "2rem" }}>
                  <div style={{ display: "inline-block", width: "16px", height: "16px", borderRadius: "50%", background: "linear-gradient(135deg, #818cf8, #6366f1)", boxShadow: "0 0 16px var(--accent)", marginBottom: "1rem" }}></div>
                  <h1 style={{ fontSize: "2rem", fontWeight: 700, color: "#fff", fontFamily: "var(--font-display)", letterSpacing: "-0.03em" }}>Cortex OS</h1>
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.9rem", marginTop: "0.25rem" }}>Knowledge Operating System for Enterprises</p>
                </div>
                <SignIn routing="hash" />
              </div>
            </div>
          </SignedOut>

          {/* Full App Workspace if Signed In */}
          <SignedIn>
            <div className="layout-container">
              <aside className="sidebar">
                <div className="logo-section">
                  <span className="logo-dot"></span>
                  <span>Cortex OS</span>
                </div>
                <nav style={{ marginTop: "2rem" }}>
                  <ul className="nav-links">
                    <li className="nav-item">
                      <a href="/">Dashboard</a>
                    </li>
                    <li className="nav-item">
                      <a href="/inbox">Approval Inbox</a>
                    </li>
                    <li className="nav-item">
                      <a href="/explorer">Knowledge Explorer</a>
                    </li>
                    <li className="nav-item">
                      <a href="/settings">Settings</a>
                    </li>
                  </ul>
                </nav>
                <div style={{ marginTop: "auto", padding: "1rem 0", borderTop: "1px solid var(--border)" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    <UserButton afterSignOutUrl="/" />
                    <div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Logged in as</div>
                      <div style={{ fontWeight: 600, color: "#fff", fontSize: "0.9rem" }}>Active User</div>
                    </div>
                  </div>
                </div>
              </aside>
              <main className="main-content">
                <MainAppWrapper>{children}</MainAppWrapper>
              </main>
            </div>
          </SignedIn>
        </ClerkProvider>
      </body>
    </html>
  );
}