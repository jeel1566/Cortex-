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

interface GraphMapProps {
  pages: PageSummary[];
  selectedId: string;
  onSelectPage: (id: string) => void;
}

function ObsidianGraphMap({ pages, selectedId, onSelectPage }: GraphMapProps) {
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const [graphData, setGraphData] = useState<any>({});
  const { getToken } = useAuth();
  
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

  useEffect(() => {
    const fetchGraph = async () => {
      try {
        const token = await getAuthToken();
        const res = await fetch("http://127.0.0.1:8000/v1/graph", {
          headers: { "Authorization": `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          setGraphData(data);
        }
      } catch (e) {
        console.error("Error fetching graph:", e);
      }
    };
    fetchGraph();
  }, [pages]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const updateSize = () => {
      canvas.width = canvas.parentElement?.clientWidth || 500;
      canvas.height = 360;
    };
    updateSize();

    const nodes = pages.map((p, idx) => {
      const angle = (idx / pages.length) * Math.PI * 2;
      const radius = Math.min(canvas.width, canvas.height) * 0.3;
      return {
        id: p.id,
        title: p.title,
        x: canvas.width / 2 + Math.cos(angle) * radius + (Math.random() - 0.5) * 30,
        y: canvas.height / 2 + Math.sin(angle) * radius + (Math.random() - 0.5) * 30,
        vx: 0,
        vy: 0,
        radius: 8,
        label: p.id
      };
    });

    const links: any[] = [];
    Object.entries(graphData).forEach(([src, relations]: [string, any]) => {
      if (relations.primary) {
        relations.primary.forEach((tgt: string) => {
          links.push({ source: src, target: tgt, type: "primary" });
        });
      }
      if (relations.secondary) {
        relations.secondary.forEach((item: any) => {
          links.push({ source: src, target: item.page, type: "secondary", condition: item.condition });
        });
      }
    });

    const validLinks = links.filter(l => 
      nodes.some(n => n.id === l.source) && nodes.some(n => n.id === l.target)
    );

    let animationFrameId: number;
    let hoveredNodeId: string | null = null;
    let draggedNode: any | null = null;
    let dragOffset = { x: 0, y: 0 };

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      if (draggedNode) {
        draggedNode.x = mouseX - dragOffset.x;
        draggedNode.y = mouseY - dragOffset.y;
        draggedNode.vx = 0;
        draggedNode.vy = 0;
        return;
      }

      let foundHover = null;
      for (const node of nodes) {
        const dist = Math.hypot(node.x - mouseX, node.y - mouseY);
        if (dist < node.radius + 6) {
          foundHover = node.id;
          break;
        }
      }

      hoveredNodeId = foundHover;
      canvas.style.cursor = foundHover ? "pointer" : "default";
    };

    const handleMouseDown = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      for (const node of nodes) {
        const dist = Math.hypot(node.x - mouseX, node.y - mouseY);
        if (dist < node.radius + 6) {
          draggedNode = node;
          dragOffset = { x: mouseX - node.x, y: mouseY - node.y };
          break;
        }
      }
    };

    const handleMouseUp = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      if (draggedNode) {
        const dist = Math.hypot(draggedNode.x - (mouseX - dragOffset.x), draggedNode.y - (mouseY - dragOffset.y));
        if (dist < 4) {
          onSelectPage(draggedNode.id);
        }
        draggedNode = null;
      }
    };

    canvas.addEventListener("mousemove", handleMouseMove);
    canvas.addEventListener("mousedown", handleMouseDown);
    window.addEventListener("mouseup", handleMouseUp);

    const tick = () => {
      const centerX = canvas.width / 2;
      const centerY = canvas.height / 2;

      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const nodeA = nodes[i];
          const nodeB = nodes[j];
          const dx = nodeB.x - nodeA.x;
          const dy = nodeB.y - nodeA.y;
          const dist = Math.hypot(dx, dy) || 1;
          
          if (dist < 200) {
            const force = 40 / (dist * dist);
            const fx = (dx / dist) * force;
            const fy = (dy / dist) * force;
            nodeA.vx -= fx;
            nodeA.vy -= fy;
            nodeB.vx += fx;
            nodeB.vy += fy;
          }
        }
      }

      validLinks.forEach(link => {
        const sNode = nodes.find(n => n.id === link.source);
        const tNode = nodes.find(n => n.id === link.target);
        if (sNode && tNode) {
          const dx = tNode.x - sNode.x;
          const dy = tNode.y - sNode.y;
          const dist = Math.hypot(dx, dy) || 1;
          const linkLen = 90;
          const springK = 0.02;
          
          const force = (dist - linkLen) * springK;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          sNode.vx += fx;
          sNode.vy += fy;
          tNode.vx -= fx;
          tNode.vy -= fy;
        }
      });

      nodes.forEach(node => {
        node.vx += (centerX - node.x) * 0.006;
        node.vy += (centerY - node.y) * 0.006;
      });

      nodes.forEach(node => {
        if (node === draggedNode) return;
        node.vx *= 0.82;
        node.vy *= 0.82;
        node.x += node.vx;
        node.y += node.vy;

        node.x = Math.max(node.radius + 6, Math.min(canvas.width - node.radius - 6, node.x));
        node.y = Math.max(node.radius + 6, Math.min(canvas.height - node.radius - 6, node.y));
      });

      const ctx = canvas.getContext("2d");
      if (ctx) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        validLinks.forEach(link => {
          const s = nodes.find(n => n.id === link.source);
          const t = nodes.find(n => n.id === link.target);
          if (s && t) {
            ctx.beginPath();
            ctx.moveTo(s.x, s.y);
            ctx.lineTo(t.x, t.y);
            if (link.type === "primary") {
              ctx.strokeStyle = "rgba(99, 102, 241, 0.4)";
              ctx.lineWidth = 1.5;
              ctx.setLineDash([]);
            } else {
              ctx.strokeStyle = "rgba(245, 158, 11, 0.35)";
              ctx.lineWidth = 1.0;
              ctx.setLineDash([4, 4]);
            }
            ctx.stroke();
          }
        });

        nodes.forEach(node => {
          const isSelected = node.id === selectedId;
          const isHovered = node.id === hoveredNodeId;

          ctx.beginPath();
          ctx.arc(node.x, node.y, node.radius + (isHovered ? 2 : 0), 0, Math.PI * 2);
          
          if (isSelected) {
            ctx.fillStyle = "#6366f1";
            ctx.shadowBlur = 15;
            ctx.shadowColor = "#6366f1";
          } else if (isHovered) {
            ctx.fillStyle = "#818cf8";
            ctx.shadowBlur = 10;
            ctx.shadowColor = "#818cf8";
          } else {
            ctx.fillStyle = "#3f3f46";
            ctx.shadowBlur = 0;
          }
          ctx.fill();
          ctx.shadowBlur = 0;

          if (isSelected || isHovered) {
            ctx.beginPath();
            ctx.arc(node.x, node.y, node.radius + 5, 0, Math.PI * 2);
            ctx.strokeStyle = isSelected ? "rgba(99, 102, 241, 0.5)" : "rgba(129, 140, 248, 0.35)";
            ctx.lineWidth = 1;
            ctx.stroke();
          }

          ctx.font = isSelected ? "bold 10px var(--font-sans), sans-serif" : "9px var(--font-sans), sans-serif";
          ctx.fillStyle = isSelected ? "#fff" : "rgba(255, 255, 255, 0.75)";
          ctx.textAlign = "center";
          ctx.fillText(node.label, node.x, node.y - node.radius - 8);
        });
      }

      animationFrameId = requestAnimationFrame(tick);
    };

    tick();

    return () => {
      cancelAnimationFrame(animationFrameId);
      canvas.removeEventListener("mousemove", handleMouseMove);
      canvas.removeEventListener("mousedown", handleMouseDown);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [pages, graphData, selectedId]);

  return (
    <div style={{ position: "relative", backgroundColor: "rgba(0,0,0,0.2)", borderRadius: "8px", border: "1px solid var(--border)", overflow: "hidden" }}>
      <canvas ref={canvasRef} style={{ display: "block" }} />
      {pages.length === 0 && (
        <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "0.85rem", color: "var(--text-secondary)" }}>
          Awaiting pages to map connection graph...
        </div>
      )}
    </div>
  );
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
    const mockPayload = { tenant_id: "tenant_a", authority_level: 5, name: "Admin (Mock Tenant)" };
    return btoa(JSON.stringify(mockPayload));
  };

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

  useEffect(() => {
    if (!selectedId) {
      setSelectedPage(null);
      return;
    }

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
          <div style={{ marginBottom: "1.5rem" }}>
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

          <div style={{ display: "grid", gridTemplateColumns: selectedPage ? "380px 1fr" : "1fr", gap: "2rem", alignItems: "start", transition: "all 0.3s ease" }}>
            
            <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
              
              <div className="card" style={{ padding: "1.25rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
                  <div>
                    <h3 style={{ fontSize: "1.1rem" }}>Obsidian Knowledge Map</h3>
                    <p style={{ color: "var(--text-secondary)", fontSize: "0.75rem" }}>Dynamic force-directed graph of page references.</p>
                  </div>
                  {selectedId && (
                    <button 
                      onClick={() => setSelectedId("")} 
                      style={{ fontSize: "0.8rem", color: "var(--accent)", background: "transparent", border: "none", cursor: "pointer", fontWeight: 600 }}
                    >
                      Reset Focus
                    </button>
                  )}
                </div>
                <ObsidianGraphMap 
                  pages={pages} 
                  selectedId={selectedId} 
                  onSelectPage={(id) => setSelectedId(id)} 
                />
              </div>

              <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                <h3 style={{ fontSize: "1.1rem" }}>Ingested Knowledge Pages</h3>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", maxHeight: "400px", overflowY: "auto", paddingRight: "4px" }}>
                  {filteredPages.map(p => (
                    <div 
                      key={p.id} 
                      onClick={() => setSelectedId(p.id)}
                      style={{ 
                        cursor: "pointer", 
                        padding: "0.75rem 1rem",
                        borderRadius: "8px",
                        border: "1px solid",
                        borderColor: selectedId === p.id ? "var(--accent)" : "rgba(255,255,255,0.05)",
                        backgroundColor: selectedId === p.id ? "var(--bg-tertiary)" : "rgba(255,255,255,0.01)",
                        transition: "all 0.2s ease"
                      }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", marginBottom: "0.25rem" }}>
                        <span style={{ fontWeight: 600, fontSize: "0.9rem" }}>{p.title}</span>
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
              </div>
            </div>

            {selectedPage ? (
              <div className="card" style={{ display: "flex", flexDirection: "column", gap: "1.5rem", opacity: loadingDetail ? 0.6 : 1, transition: "opacity 0.15s ease" }}>
                
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start", borderBottom: "1px solid var(--border)", paddingBottom: "1rem" }}>
                  <div>
                    <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>{selectedPage.id}</div>
                    <h2 style={{ fontSize: "1.75rem", marginTop: "0.25rem" }}>{selectedPage.title}</h2>
                  </div>
                  <button 
                    onClick={() => setSelectedId("")} 
                    style={{ 
                      background: "transparent", 
                      border: "none", 
                      color: "var(--text-secondary)", 
                      cursor: "pointer", 
                      fontSize: "1.5rem",
                      padding: "0.25rem 0.5rem",
                      borderRadius: "4px",
                      transition: "all 0.2s"
                    }}
                    onMouseEnter={(e) => e.currentTarget.style.color = "#fff"}
                    onMouseLeave={(e) => e.currentTarget.style.color = "var(--text-secondary)"}
                  >
                    ✕
                  </button>
                </div>

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
            ) : (
              <div className="card" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "350px", padding: "4rem 2rem", textAlign: "center", borderStyle: "dashed", borderColor: "rgba(255,255,255,0.12)" }}>
                <div>
                  <div style={{ fontSize: "2.5rem", marginBottom: "1rem" }}>🕸️</div>
                  <h3 style={{ fontSize: "1.2rem", marginBottom: "0.5rem" }}>No Page Selected</h3>
                  <p style={{ color: "var(--text-secondary)", fontSize: "0.85rem", maxWidth: "320px", margin: "0 auto" }}>
                    Select a node on the Obsidian graph map or pick a page from the list to inspect version logs, Git audit history, and redaction clearance.
                  </p>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
