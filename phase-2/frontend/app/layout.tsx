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
            <div style={{ display: "flex", minHeight: "100vh", alignItems: "center", justifyContent: "center", background: "var(--bg-primary)" }}>
              <div style={{ width: "100%", maxWidth: "440px", padding: "3rem 2.5rem", background: "var(--bg-secondary)", borderRadius: "16px", border: "1px solid var(--border)", boxShadow: "0 20px 50px rgba(0,0,0,0.5)" }}>
                <div style={{ textAlign: "center", marginBottom: "2.5rem", display: "flex", flexDirection: "column", alignItems: "center" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: "5px", width: "36px", marginBottom: "1rem" }}>
                    <div style={{ height: "4px", backgroundColor: "var(--accent)" }}></div>
                    <div style={{ height: "4px", backgroundColor: "var(--accent)" }}></div>
                    <div style={{ height: "4px", backgroundColor: "var(--accent)" }}></div>
                  </div>
                  <h1 style={{ fontSize: "2.25rem", fontWeight: 500, color: "var(--text-primary)", fontFamily: "var(--font-display)", letterSpacing: "0.05em", textTransform: "uppercase" }}>Cortex</h1>
                  <span className="logo-subtitle" style={{ marginTop: "0.25rem" }}>Knowledge OS</span>
                </div>
                <SignIn routing="hash" />
              </div>
            </div>
          </SignedOut>

          {/* Full App Workspace if Signed In */}
          <SignedIn>
            <div className="layout-container">
              <aside className="sidebar">
                <div className="logo-section" style={{ paddingBottom: "1.5rem", borderBottom: "1px solid var(--border)" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: "6px", width: "40px", marginBottom: "0.75rem" }}>
                    <div style={{ height: "5px", backgroundColor: "var(--accent)" }}></div>
                    <div style={{ height: "5px", backgroundColor: "var(--accent)" }}></div>
                    <div style={{ height: "5px", backgroundColor: "var(--accent)" }}></div>
                  </div>
                  <span>Cortex</span>
                  <span className="logo-subtitle">Knowledge OS</span>
                </div>
                <nav style={{ marginTop: "1rem" }}>
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