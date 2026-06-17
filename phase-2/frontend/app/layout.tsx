import { ClerkProvider, SignedIn, SignedOut, SignInButton, SignUpButton, UserButton } from "@clerk/nextjs";
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
                </ul>
              </nav>
              <div style={{ marginTop: "auto", padding: "1rem 0", borderTop: "1px solid var(--border)" }}>
                <SignedOut>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    <SignInButton mode="modal">
                      <button className="btn btn-primary" style={{ width: "100%", cursor: "pointer" }}>Sign In</button>
                    </SignInButton>
                    <SignUpButton mode="modal">
                      <button className="btn btn-outline" style={{ width: "100%", cursor: "pointer" }}>Sign Up</button>
                    </SignUpButton>
                  </div>
                </SignedOut>
                <SignedIn>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                    <UserButton afterSignOutUrl="/" />
                    <div>
                      <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)" }}>Logged in as</div>
                      <div style={{ fontWeight: 600, color: "#fff", fontSize: "0.9rem" }}>Active User</div>
                    </div>
                  </div>
                </SignedIn>
              </div>
            </aside>
            <main className="main-content">{children}</main>
          </div>
        </ClerkProvider>
      </body>
    </html>
  );
}