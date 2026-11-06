[Page 1]AGILE OPERATIONAL PLAN INTERNAL TEAM DISTRIBUTION
Kifi Platform: Team Sprint Roadmap & Task Allocation
Execution Period: Nov 03, 2026-Jan 17, 2027. Exams Recess: Nov 14-Nov 21, 2026 Cycle: 1-Week Cadence (Sprint 1: 10-Day
Pre-Exam Sprint)
1. WEEKLY SPRINT EXECUTION & CODE REVIEW PROTOCOL
Each sprint operates on a synchronized weekly timeline structured to guarantee thorough code quality, prevent merge bottlenecks, and
provide buffer for refactoring before merging to dev (with Sprint 1 calibrated as a 10-day pre-exam sprint from Nov 03 to Nov 13):
1. Kickoff:
Sunday at 10:00 PM (Sprint 1
2. Dev Deadline:
Thursday at 4:00 PM (Sprint 1:
Wed Nov 11, 4 PM). Code freeze
and PR opened.
3. Code Review:
4. Fixes & Merge:
Thu 4:00 PM Friday. Assigned
reviewer inspects PR and leaves
change requests.
Sat (Fixes)
Sunday at 4:00 PM.
Final approval, Cl check, and
merge to dev.
kicked off Tue Nov 03). Jira
backlog activation.
2. TEAM MEMBER OWNERSHIP & CORE SCOPES
Aymen
(M1)
UI/UX & Master UI Shell
Figma design system,
token library, global
layout components,
navbars, and reusable
web primitives.
Moncef
(M2)
RAG & Darija NLP Lead
PIl sanitization regexes,
burst debouncing, Qdrant
vector schemas, and
Darija/Arabizi style
prompts.
Ayoub
(M3)
Integrations & Bridge
OAuth (Google/Meta),
MTProto extractor, Reddit
OAuth, RAG WebSockets,
Telegram bot, and live
social egress.
Chouaib
(M4)
FastAPI & Developer API
FastAPI containerization,
JWT auth engine, CRUD
endpoints, Developer API
keys, and Redis rate
limiting.
3. SPRINT BREAKDOWN: FOUNDATION & INGESTION PHASE
Mouatez
(M5)
Database & Full-Stack
SQLAlchemy ORM
models, in-memory ZIP
extractor, Ul-backend
wiring, and Chargily Pay
V2 integration.
Sprint 1: Architecture, Ingestion Foundation & Design Sprint (10- Nov 03 (Kickoff) - Nov 13 (4 PM) PR Deadline: Wed Nov 11, 4 PM-
Day Pre-Exam Sprint)
Review: Thu Nov 12.
Aymen
Rev: Mouatez
Moncef
Rev. Ayoub
Ayoub
Rev: Chouaib
Chouaib
Figma Master Design
PII & profanity
Google & Meta OAuth
System: tokens,
sanitization regexes
backend flows +
typography, UI
(05/06/07, CCP/RIP, IDs)
components, Landing
Page, Auth views, and
+ message debouncer
logic (120s paired
Telegram MTProto client
auth handshake
Rev: Ayoub
FastAPI skeleton with
Docker Compose, Cl
setup, LLM client
(Telethon) to pull
Persona Wizard
blocks).
historical chats.
wrapper + JWT auth
engine (/register, /login,
/me).
wireframes.
Mouatez
Rev: Moncef
PostgreSQL schema
(Users, Workspaces,
Personas, Alembic) + in-
memory ZIP archive
parser (extract
conversation lists).
EXAM RECESS (Nov 14-Nov 21, 2026): Formal project freeze for academic exams. No sprint shifts, commits, or deliverables.
Sprint 2: Vector DB, Reddit Ingestion & Interactive Conversation Nov 22 (10 PM) Nov 29 (4 PM) PR Deadline: Thu Nov 26, 4 PM
Selector Ul
Aymen
Rev: Mouatez
Moncef
Rev: Ayoub
Init Next.js repo +
Tailwind. Build core
dashboard shell (sidebar,
workspace switcher) and
mockups for Chat
Drawer.
Odrarit/Milvus vector
collections setup:
schema definitions,
embedding ingestion
pipeline, and metadata
isolation.
Review: Fri Nov 27
Rev: Chouaib
Ayoub
Reddit OAuth2
integration & PM
extractor. OAuth
handshake and direct
extraction of private
message histories.
Chouaib Rev: Moncef
Persona CRUD endpoints
(POST/GET/DELETE
/personas), behavioral
rules storage models,
and token blacklist logic.
Rev. Aymen
Mouatez
Drag-and-drop ZIP
upload Ul with progress
tracking + interactive
Conversation Selector
Table wired to backend
ZIP parser.
Kifi Platform Team Sprint Roadmap & Task Allocation
Section 1-3 Page 1 of 3
[Page 2]Sprint 3: Darija RAG Pipeline, WebSocket Bridge & Rules Wizard
Aymen
Rev: Mouatez
Privacy Wizard Ul
(Yes/No toggles for
personal details) and
Hardcoded Prompt Rules
inputs (negative prompt
builder).
Moncef
Rev: Ayoub
Darija/Arabizi style-
conditioning prompt
engine: enforce script
choices, extract user
vocabulary patterns, and
build RAG prompts.
Nov 29 (10 PM) Dec 06 (4 PM) PR Deadline: Thu Dec 03, 4 PM
Ayoub
Rev: Chouaib
RAG WebSocket service:
real-time streaming
bridge between FastAPI
backend and RAG
generation for low-
latency tokens.
Chouaib
Rev. Mouatez
Asynchronous indexing
worker queue (FastAPI
Background Tasks/Celery)
to manage task states
(pending, indexing,
ready).
Mouatez Rev. Aymen
Wire Privacy Wizard and
Hardcoded Rules forms
to persona backend
routes. Model database
entities for negative
constraints.
Architecture, In-App Playground & Verification Dec 06 (10 PM) Dec 13 (4 PM) PR Deadline: Thu Dec 10, 4 PM
Sprint 4: Developer API
Aymen
Rev. Mouatez
Moncef
"My Agents" dashboard
page (agent cards,
status badges, "Connect
Agent action buttons)
and layout template for
Developer Portal.
Rev. Ayoub
Structured JSON output
generator (confidence
scores, escalation flags,
messages_to_send:
[str]). Pre-deployment
test loop.
Ayoub
Rev: Chouaib
Developer Inference backend
service for POST
/api/v1/agents/ id /generate-
reply: payload validation, RAG
execution, bursts.
Rev: Mouatez
Chouaib
Developer API Key
Management: key
generation, SHA-256
storage, API routes
(POST/GET/keys),
Redis rate-limiting,
APIKeyHeader.
Mouatez Rev: Chouaib
Build and wire both the
In-App Testing Chat
Drawer (streaming from
Ayoub's service) and the
Developer API Keys &
Docs Ul.
Sprint 5: Telegram Bot Escalation & Whitelisting Logic
Aymen
Rev. Mouatez
Contact Whitelisting Ul:
table allowing users to
select specific
contacts/groups, assign
personas, and toggle
Read-Only vs. Auto-Reply.
Moncef
Rev: Ayoub
High-Traffic Group Chat
Summarizer: token-
efficient chunking of
$200+$ message threads,
filtering noise into 3-5
bullet digests.
Dec 13 (10 PM) Dec 20 (4 PM) PR Deadline: Thu Dec 17, 4 PM
Ayoub
Rev. Moncef
Telegram Escalation Bot:
interactive cards with
inline buttons [Send
Suggested], [Takeover],
and voice/text
instruction listener.
Chouaib
Rev: Mouatez
Contact Whitelist CRUD
endpoints
(GET/POST/PUT/DELETE
/whitelist) and escalation
event logging endpoints.
Mouatez Rev. Chouaib
Model ContactWhitelist
and EscalationLog
entities in PostgreSQL
Wire Whitelisting
frontend views to
backend API routes.
Sprint 6: Chargily Pay V2
Aymen
Rev: Ayoub
"Connect Agent" modal
and documentation
drawer: step-by-step
guides for connecting
Telegram, IG Creator,
Reddit with status
badges.
Integration & Platform Linking
Moncef
Rev: Ayoub
Prompt Injection Defense
& Data Shield: security
filters preventing
adversarial prompts from
bypassing boundaries or
leaking chats.
Dec 20 (10 PM) Dec 27 (4 PM) PR Deadline: Thu Dec 24, 4 PM
Ayoub Rev: Chouaib
Live Social Connector
framework: implement
live messaging hooks for
Telegram MTProto and
setup Instagram Creator
Webhooks.
Chouaib
Rev Mouatez
Global "Emergency
Pause" switch endpoint
to halt automated replies
immediately. Configure
Redis pub/sub to notify
workers.
Mouatez
Rev: Chouaib
Integrate Chargily Pay V2
API (checkout session &
webhook signature
verification). Build
frontend Billing Ul and
balance updates.
Sprint 7: Full Social Egress, Group Summaries & Webhooks
Aymen
Rev: Mouatez
"Digests & Summaries 
dashboard view (bullet
digests with source tags)
and wire the Emergency
Pause button on the top
navbar
Moncef
Rev: Chouaib
Context-pruning & token
optimization: dynamic
few-shot example
selection to cut query
token costs by 30% while
keeping dialect fidelity.
Dec 27 (10 PM) - Jan 03 (4 PM) PR Deadline: Thu Dec 31, 4 PM
Ayoub
Rev: Mouatez
Wire Telegram Bot to
Group Summarizer:
automated daily digests
and/summarize
command. Finalize
Instagram and Reddit
outbound dispatchers.
Chouaib
Rev: Aymen
Public Developer
Documentation portal
(interactive
Swagger/Redoc) with
curl, Python, and JS code
examples for the
inference API.
Mouatez Rev. Ayoub
Wire Digests Ul to
backend summarization
endpoints. Complete
transaction ledger history
and invoice receipt
downloads on UI.
Sprint 8: System Hardening, Data Sovereignty & Load Testing
Aymen Rev: Mouatez
Frontend accessibility &
responsive audit:
optimize mobile views,
add skeleton loaders,
toast alerts, and fix
cross-browser styling.
Moncef
Rev: Ayoub
End-to-end linguistic
evaluation: benchmark
100 test chats across
Arabizi, Darija, and
French mixing for
consistency and zero
MSA.
Jan 03 (10 PM) - Jan 10 (4 PM) PR Deadline: Thu Jan 07, 4 PM
Ayoub
Rev: Chouaib
Test integration edge
cases: Telegram
disconnections, webhook
retries, rate limits, and
Telegram Bot button
callback recovery.
Chouaib
Rev: Mouatez
API stress testing using
Locust/k6 (100
concurrent requests).
Configure production
security headers, CORS,
and SSL termination.
Mouatez Rev: Moncef
Data Sovereignty &
Account Purge pipeline:
cascading delete
removing all vectors,
relational records, and
tokens in one
transaction.
Kifi Platform Team Sprint Roadmap & Task Allocation
Section 4 Page 2 of 3
[Page 3]Sprint 9: Final Deployment, Documentation & Evaluation Delivery
| All  Aymen  Final Ul validation across  devices, design-to-  production consistency  review, and preparation  of final presentation  mockups.   | Moncef  All  Final tuning of vector  similarity thresholds and  documentation of the  Darija/Arabizi prompt  engineering strategy.   | Ayoub  All  Finalize Developer API  documentation, test end-  to-end Telegram bot  flows, and verify social  integration stability.   | Chouaib  All  Production cloud  deployment, setup  automated Docker  container health checks,  and verify database  automated backups.   | Mouatez  All  Final end-to-end  integration walk-through  (Auth Upload → Select  →Train Test →  Deploy Pay) with zero  console errors.   |
Jan 10 (10 PM) Jan 17 (4 PM) Final Deadline: Sun Jan 17, 4 PM
4. PEER REVIEW & CODE GOVERNANCE MATRIX
| Author   | Primary Domain   | Assigned Code Reviewer   | Primary Review Responsibilities   |
| Aymen   | Frontend UI/UX & Master Shell   | Mouatez (Full-Stack Connector)   | Design token consistency, responsive CSS  states, component modularity.   |
| Moncef   | RAG, NLP & Vector Indexing   | Ayoub (Integrations & Bridge)   | PII regex coverage, debounce window accuracy,  vector metadata scoping.   |
| Ayoub   | Integrations, OAuth & Telegram   | Chouaib (Backend Lead)   | WebSocket stability, OAuth redirect safety, async  event handling.   |
| Chouaib   | FastAPI, DevOps & Developer API   | Mouatez (DB Architect)   | JWT security, API key hashing, Redis rate-  limiting correctness.   |
| Mouatez   | Database, Full-Stack & Billing   | Aymen (UI) / Chouaib (API)   | Alembic migration safety, Chargily webhook  verification, zero raw SQL.   |
Kifi Platform Team Sprint Roadmap & Task Allocation
Section 4 Page 3 of 3