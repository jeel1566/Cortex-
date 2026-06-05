Cortex
UI and UX Design Document  ·  v1.0  ·  May 2026

# 1. Design Principles

# 2. Colour System

# 3. Typography

# 4. Product Surfaces
## 4.1 Dashboard — Knowledge Health
The main view. Not a search interface. A living map of the company's knowledge state.
Knowledge health score — % of pages current, conflict-free, validated, and linked
Recent changes — what updated in last 24 hours, who approved it, confidence score
Pending approvals — changes drafted by system awaiting human sign-off (count badge)
Active conflicts — pages with detected contradictions, sorted by severity and last queried
Coverage gaps — topics agents ask about frequently with no matching page
Agent query volume — which pages are hit most, which are never queried (stale candidates)
Feedback queue — wrong answers flagged by agents, awaiting re-synthesis

## 4.2 Knowledge Explorer — The Graph
Visual graph of the knowledge base. Built from scratch. Not Obsidian.
Nodes are pages — coloured by access level (blue=team, green=public, amber=department, red=confidential)
Node size — proportional to query frequency (bigger = more used)
Solid edges — primary links (always follow)
Dashed edges — secondary links (conditional)
Click a node — full page card slides in from right: content, YAML header, synthesis scores, change history
Click an edge — shows the condition that triggers it (for secondary links)
Filter by: chapter, access level, owner, conflict status, validation score, date range
Semantic search — type a question, graph animates to show entry page and predicted traversal path

## 4.3 Approval Inbox — The Core Human Interface
This is where humans spend 10 seconds per day. Designed for mobile-first, one-handed operation.
Each card shows: what changed in plain English, what it changed from, which source triggered it, confidence score
Diff view — before and after side by side with changes highlighted
Source card — the original Slack message or doc that triggered the change, with author and timestamp
Three actions: Approve (green, swipe right), Reject (red, swipe left), Edit (amber, tap to modify draft before approving)
Priority queue — critical changes at top, standard below, background collapsed
Conflict cards — two conflicting pages shown side by side with conflict type labeled and resolution suggestion

## 4.4 Page Detail View
Full view of one knowledge page. Every piece of information visible.
Header: page title, version number, last updated, owner, access level badge
Status row: validation scores (coverage %, hallucination %, completeness score), conflict flags, feedback count
Content: full markdown page text with propositions highlighted and their sensitivity levels shown on hover
Links panel: primary links as solid cards, secondary links with condition displayed
History: collapsed by default, expandable to see full diff on every version
Sources: original documents the page was synthesised from, with timestamps and authors
Actions: flag as outdated, suggest edit, see all queries that hit this page

## 4.5 API Playground — Developer Surface
Live query interface — type any question, see the real API JSON response
Traversal visualiser — animated graph showing which pages were read, in what order, why
Latency breakdown — time spent on embedding, HNSW, traversal, assembly
Response inspector — full response JSON with every field explained
SDK snippets — Python, JavaScript, curl auto-generated for every query
MCP tool explorer — browse available tools and see their descriptions
Auth tester — test different authority levels to see how responses change

# 5. Component Library
## 5.1 Page Card
┌──────────────────────────────────────────────────────┐
│ [TEAM] [v3] [✓ VALIDATED]   Standard Refund Policy  │
│ Finance team  ·  Updated Jan 15 2026  ·  Hit 847x    │
├──────────────────────────────────────────────────────┤
│ Our standard refund window is 60 days from purchase  │
│ date for all customers. Refunds must be requested    │
│ via the support portal with order number...          │
├──────────────────────────────────────────────────────┤
│ ● Primary: VIP Exceptions (page_042)                 │
│ ○ Secondary: Damaged Goods (if: damaged/defect)      │
│ ○ Secondary: Late Delivery (if: late/delayed)        │
├──────────────────────────────────────────────────────┤
│ Synthesis: 94% coverage · 0% hallucination · 8.5/10  │
└──────────────────────────────────────────────────────┘

## 5.2 Traversal Path
Query: What is our refund policy for VIP customers?
─────────────────────────────────────────────────────
Index lookup          3ms   → entry: page_013
page_013 Refund Policy       ● primary link →
page_042 VIP Exceptions      ● primary link →
page_071 Enterprise Approval ○ secondary [condition: enterprise matched]
─────────────────────────────────────────────────────
Total: 28ms  ·  3 pages read  ·  Confidence: 0.91

## 5.3 Conflict Card
⚠ TEMPORAL CONFLICT  ─────────────────────────────────
Page 013 (Jan 2026, Finance team)
  "Refund window is 60 days"
Page 022 (Nov 2021, Support team)  
  "Refund window is 30 days"
─────────────────────────────────────────────────────
Resolution: Page 013 is newer. Displaying as current.
[Confirm]  [View Both]  [Override]

## 5.4 Approval Card
STANDARD APPROVAL  ─────────────────────────────────────
Refund window changed from 30 days → 60 days
Triggered by: Slack #finance · Jan 15 2026 · @sarah.chen
Confidence: 0.94  ·  Synthesis validation: PASSED
─────────────────────────────────────────────────────
BEFORE: Our standard refund window is 30 days...
AFTER:  Our standard refund window is 60 days...
─────────────────────────────────────────────────────
[✓ APPROVE]          [✎ EDIT]          [✗ REJECT]

# 6. Mobile Design
Approval inbox is the primary mobile surface — full screen, one card at a time
Swipe right to approve, swipe left to reject, tap to edit — maximum three taps for any action
Push notifications when critical approvals arrive — with preview in notification
Knowledge Explorer graph is desktop only — too complex for small screens
Page detail view is read-only on mobile — no editing
API playground is desktop only

### Table
Principle | What it means in practice
Transparent by default | Every answer shows which pages were read, in what order, and why. Never a black box.
Trust through auditability | Agents and humans always see the source, the traversal path, the confidence score, and any conflict flags.
Minimal human friction | The only human job is approving changes the system drafted. One click. Never writing from scratch.
Errors are valuable signals | Conflicts, gaps, low confidence, and wrong answers are shown prominently — not hidden. They improve the system.
Progressive disclosure | Simple by default. Full depth available on demand. Never overwhelming unless the user wants it.



### Table
Token | Hex | Usage
Primary Blue | #1a4f8a | Headers, primary actions, links, HNSW visual, brand
Primary Green | #1a6b4a | Healthy status, approved pages, primary links, success states
Amber | #8a5a1a | Warnings, pending approvals, secondary links, needs review
Red | #8a1a1a | Conflicts, errors, genuine contradictions, revoked tokens
Ink | #0a0a0a | All body text
Muted | #6b6560 | Secondary text, metadata, timestamps, labels
Paper | #f7f5f0 | Page background
Cream | #fafbfd | Card backgrounds, table alternating rows
Light Blue | #e8f0fa | Table headers, info highlights, active states



### Table
Element | Font | Size | Weight | Usage
Display title | Syne | 48-72px | 800 | Cover pages, hero sections
Section heading H1 | Syne | 30-36px | 700 | Major sections
Sub-heading H2 | Syne | 22-28px | 600 | Sub-sections
Card title H3 | Syne | 16-20px | 600 | Card and component headings
Body text | Instrument Sans | 14-16px | 400 | All readable content
Body light | Instrument Sans | 14px | 300 | Descriptions, secondary copy
Label / badge | Syne | 10-11px | 600 + uppercase + tracking | Status badges, eyebrows, tags
Code / YAML | JetBrains Mono | 13px | 400 | All code, page YAML headers
Metadata | Instrument Sans | 12px | 300 | Timestamps, version numbers, IDs

