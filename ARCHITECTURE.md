# Kyron Medical AI Clinical Scribe — Architecture

> Last updated: June 2026  
> Live URL: **https://scribe.lambdapen.com** (AWS EC2, us-east-1)

---

## 1. System Overview

Kyron Scribe is a provider-facing AI clinical documentation platform. A physician or clinical staff member pastes or types a raw encounter transcript; the AI streams a structured SOAP note (Subjective · Objective · Assessment · Plan) in real time, including semantically matched ICD-10 codes. All data persists in AWS RDS PostgreSQL. The platform is multi-tenant by role: **Providers** own their encounters; **Admins** oversee the entire roster and note-template library.

---

## 2. Infrastructure

```
Internet
  │  HTTPS 443 (Let's Encrypt TLS, HSTS)
  ▼
┌────────────────────────────────────────────────────────┐
│  EC2  t3.medium  (Ubuntu 22.04)                        │
│                                                        │
│  nginx 1.18                                            │
│  ├─ rate-limit login: 5 req/min per IP (burst 3)       │
│  ├─ security headers: CSP · HSTS · X-Frame · XSS       │
│  ├─ /api/*  → proxy_pass 127.0.0.1:8000               │
│  │            proxy_buffering off  (SSE support)        │
│  │            proxy_read_timeout 300s                   │
│  └─ /       → React SPA (dist/)                        │
│                                                        │
│  uvicorn  (1 worker, port 8000)                        │
│  └─ FastAPI application                                │
└────────────────────────────────────────────────────────┘
         │  VPC-internal only  │
         ▼                     ▼
  AWS RDS PostgreSQL 15   AWS Secrets Manager
  (private subnet,        scribe/prod
   not publicly           ├─ DB_URL
   accessible)            ├─ JWT_SECRET
                          └─ ANTHROPIC_API_KEY
```

**Key infrastructure facts:**
- RDS is in a private VPC subnet — zero public internet access
- All secrets loaded at startup via Secrets Manager; no `.env` files, no hardcoded values
- Connection pool: `pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`, `pool_recycle=3600s`
- TLS via Let's Encrypt (certbot auto-renewal); HSTS enforced (`max-age=31536000`)
- nginx hides server version, adds `Content-Security-Policy`, `Permissions-Policy`

---

## 3. Technology Stack

| Layer | Choice | Rationale |
|-------|--------|-----------|
| Backend | **FastAPI** (Python 3.12) | Async-native, automatic OpenAPI, excellent SSE support |
| ORM | **SQLAlchemy 2.0** (mapped_column) | Type-safe, explicit relationship loading, connection pooling |
| Database | **PostgreSQL 15** on AWS RDS | JSONB for flexible note content, pgvector-ready, ACID guarantees |
| AI | **Anthropic Claude 3.5 Haiku** | Tool-use for patient history retrieval, fast streaming |
| Frontend | **React 18 + Vite + Tailwind CSS** | SPA, React Router v6, component-level state |
| Auth | **JWT HS256** (8-hour expiry) | Stateless, `session_version` claim for single-session enforcement |
| Proxy | **nginx** | Rate limiting, SSE streaming, TLS termination, security headers |

---

## 4. Database Schema (ERD)

```
providers
  id PK · first_name · last_name · email UNIQUE · password_hash
  role ENUM(provider,admin) · is_active · session_version · created_at

patients
  id PK · first_name · last_name · dob
  UNIQUE(first_name, last_name, dob)          ← identity key for upsert

templates
  id PK · name · system_prompt TEXT · is_active · updated_at

encounters
  id PK
  patient_id  FK→patients   [INDEX]
  provider_id FK→providers  [INDEX]
  template_id FK→templates  NULL
  status ENUM(draft,saved) · raw_input TEXT
  created_at · updated_at

notes
  id PK · encounter_id FK→encounters UNIQUE   ← one note per encounter

note_versions
  id PK · note_id FK→notes · version_no INT
  content JSONB                               ← {subjective,objective,assessment,plan,icd10_codes,__label}
  saved_by FK→providers · saved_at
  INDEX(note_id, version_no)                  ← fast version-history lookup
  Immutable — versions are never updated or deleted

drafts
  id PK · encounter_id FK→encounters UNIQUE   ← one live draft per encounter
  provider_id FK→providers
  content JSONB                               ← same shape as note_versions.content
                                                + _transcript + _label
  updated_at                                  ← auto-updated on every save

icd10_codes
  code PK · description · embedding JSONB     ← pre-computed vector for semantic search

audit_log
  id PK · actor_id FK→providers NULL
  action VARCHAR · target_type · target_id
  metadata JSONB · created_at
```

**Schema design decisions:**
- `Note` is a container; content lives only in immutable `NoteVersion` rows — versions are never overwritten
- `Draft` is a mutable scratch-pad; one per encounter, upserted on every keystroke/autosave
- `Draft.content` stores the full workspace state (`_transcript`, `_label`, all SOAP fields) so the exact in-progress state is restored on any device
- `encounters.raw_input` holds the transcript at time of last generation (used for `is_invalid` detection when no NoteVersion exists)
- `icd10_codes.embedding` stores a 384-dim float vector as JSONB; cosine similarity computed in Python — no pgvector extension required at this scale
- `providers.session_version` is an integer counter, embedded in every JWT as claim `sv`; incremented on each login to invalidate all prior tokens

---

## 5. Authentication & Session Model

### 5.1 JWT structure
```json
{
  "sub": "3",
  "role": "provider",
  "sv": 7,
  "exp": 1749999999
}
```

Every protected endpoint calls `get_current_provider`, which:
1. Decodes and validates the JWT signature
2. Looks up the provider by `sub`
3. Compares `payload["sv"]` against `provider.session_version` in the DB
4. Returns `401 "Session superseded by a newer login"` if they diverge

### 5.2 Single-session enforcement
Only one active session per provider account at a time. The mechanism:

```
Login(Device B)
  │
  ├─ notify SSE clients: "flush"   ← Device A's draft saved (token still valid)
  ├─ asyncio.sleep(1.5 s)          ← grace period for save round-trip
  ├─ session_version += 1          ← all prior tokens now invalid
  ├─ issue new JWT (sv = new)
  └─ notify SSE clients: "superseded"  ← Device A shows overlay / redirects
```

### 5.3 SSE session stream (`GET /api/auth/session-stream`)
Each logged-in client holds a persistent HTTP connection to this endpoint. The server pushes events as plain-text SSE. A 25-second keepalive comment (`: keepalive`) prevents nginx from closing the connection. The frontend reconnects automatically after any drop.

### 5.4 Frontend session handling
| Location | On `flush` | On `superseded` |
|----------|-----------|-----------------|
| Workspace (`/encounter/:id`) | `flushDraftKeepAlive()` — saves draft while token valid | Orange overlay: "Signed In on Another Device" |
| Other pages | (no handler needed) | Redirect to `/login?reason=superseded` |
| Login page | — | Banner: "Your account was signed in on another device" |

Token expiry (8h, not superseded) shows a blue "Session Expired" overlay / `?reason=expired` banner instead.

---

## 6. Core AI Workflow

```
Provider pastes transcript
       │
       ▼
has_clinical_content(transcript)?
  • word count ≥ 10
  • ≥ 3 clinical keyword matches
  • ≥ 1 anchor term (patient/exam/visit/…)
       │
  NO ──┤──► Return INSUFFICIENT_RESPONSE immediately
  YES  │
       ▼
POST /api/encounters/generate  (SSE)
       │
       ▼
Claude claude-3-5-haiku-20241022
  system: role + template system_prompt + ICD-10 instruction
  user:   transcript
  tools:  get_patient_history(patient_id)
       │
       ├─ tool_use block →  query DB for prior NoteVersions
       │                    return JSON history to Claude
       ▼
  streaming text_delta events → frontend renders progressively
       │
       ▼
  JSON parsed from stream → setNote() → live SOAP display
```

**Patient context injection** is handled by Claude via a tool call — not by pre-stuffing history into the prompt. Claude decides whether to call `get_patient_history` based on the encounter. Returning patients get prior diagnoses/treatments referenced where clinically appropriate; the AI demonstrably behaves differently.

**Template system**: The `template_id` from the request is always fetched fresh from the DB at generate-time, not from frontend state. This ensures admin template edits take effect on the provider's *next* generation without a page refresh. The template picker also re-fetches the list when opened, so newly created templates appear immediately.

---

## 7. Draft Persistence

Draft auto-save fires on every note field change (debounced) plus:
- Every 30 seconds (interval)
- On `beforeunload` (page refresh / tab close) via `fetch` with `keepalive: true`
- On `kyron:session-flush` event (pre-supersession, while token is still valid)

On page load (or cross-device login), the encounter fetch returns the draft and the workspace restores the exact transcript, SOAP fields, and version label.

---

## 8. Non-Happy-Path Scenarios

| Scenario | Detection | Behaviour |
|----------|-----------|-----------|
| **Clinically empty transcript** | `has_clinical_content()` → false | INSUFFICIENT_RESPONSE returned; red "Invalid draft" badge in patient history |
| **Session expired (8h timeout)** | 401 on any API call; workspace SSE timeout | Blue "Session Expired" overlay; draft preserved; redirect-after-login restores exact URL |
| **Session superseded (another device)** | SSE `superseded` event (< 1 s) | Orange "Signed In on Another Device" overlay on workspace; draft flushed before invalidation; `?reason=superseded` banner on login page |
| **Account deactivated mid-session** | 403 `Account deactivated` on any API call | Yellow "Account Deactivated" overlay; draft readable/copyable; no data loss |
| **Invalid draft saved** | INSUFFICIENT_RESPONSE markers in NoteVersion | Red "Invalid draft" badge; save button disabled; warning banner in workspace |

---

## 9. API Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/auth/login` | — | Authenticate; two-phase session supersession |
| GET | `/api/auth/me` | JWT | Current user info |
| GET | `/api/auth/session-stream` | JWT | Long-lived SSE for instant session events |
| POST | `/api/encounters` | Provider | Create encounter (upserts patient) |
| GET | `/api/encounters` | Provider | List own encounters with draft/invalid status |
| GET | `/api/encounters/:id` | Provider | Load encounter + note + draft |
| POST | `/api/encounters/generate` | Provider | Stream SOAP note via SSE |
| POST | `/api/encounters/save` | Provider | Save note version (immutable) |
| PUT | `/api/drafts` | Provider | Upsert draft content |
| GET | `/api/icd10/search?q=` | Provider | Semantic ICD-10 code search |
| GET | `/api/admin/providers` | Admin | List all providers |
| POST | `/api/admin/providers` | Admin | Create provider account |
| PATCH | `/api/admin/providers/:id/deactivate` | Admin | Deactivate provider |
| GET | `/api/admin/encounters` | Admin | All encounters with invalid/draft flags |
| GET | `/api/admin/templates` | Admin | List note templates |
| POST | `/api/admin/templates` | Admin | Create template |
| PATCH | `/api/admin/templates/:id` | Admin | Edit template (live, no refresh needed) |
| DELETE | `/api/admin/templates/:id` | Admin | Soft-delete template |

---

## 10. Pioneer Features (beyond requirements)

| Feature | Description |
|---------|-------------|
| **Single-session enforcement** | `session_version` counter in DB + JWT claim; only one device active per account at a time |
| **SSE-based instant push** | Real-time server push replaces polling; supersession detected in < 1 second |
| **Two-phase supersession** | Backend flushes Device A's draft before invalidating the session; no content lost when switching devices |
| **Invalid draft detection** | Validates transcript with keyword/anchor heuristic pre-generation; shows red "Invalid draft" badge in admin and provider views without requiring a generation attempt |
| **Draft validity indicators** | Color-coded status across all views: 🟢 Normal, 🟡 Draft in progress, 🔴 Invalid draft — with alignment grid in admin list |
| **Admin status overview** | Per-patient dot-badge row (green/yellow/red) in admin All Patients list with color legend |
| **Rate-limited login** | nginx `limit_req_zone` at 5 req/min per IP; brute-force protection at the proxy layer |
| **Security hardening** | Full security header suite (CSP, HSTS, X-Frame-Options, Referrer-Policy, Permissions-Policy); nginx version hidden |
| **Version labels** | Providers tag note versions with up to 4-word labels for quick identification in the history panel |
| **Redirect-after-login** | `sessionStorage.redirectAfterLogin` restores the exact encounter URL after session expiry or supersession |
| **Audit logging** | Full audit trail: login, provider create/deactivate, template create/edit/delete, note save |
| **Template live reload** | Template picker re-fetches from DB on open; new templates visible immediately without page refresh |

---

## 11. Security Model

- **Secrets**: all credentials in AWS Secrets Manager (`scribe/prod`); loaded at runtime; never in source or `.env`
- **Tokens**: HS256 JWT, 8-hour expiry, `session_version` claim prevents replay after re-login
- **Transport**: TLS 1.2/1.3 enforced; HSTS 1-year with subdomains
- **Headers**: CSP restricts sources to `self`; `frame-ancestors 'none'`; permissions deny camera/mic/geo
- **Rate limiting**: 5 login attempts/min per IP at nginx layer
- **Role enforcement**: every endpoint checks JWT role; providers cannot access admin routes or other providers' data
- **RDS isolation**: PostgreSQL in private VPC subnet; EC2 is the only allowed inbound source
- **Account deactivation**: `is_active=false` checked on every request, not just at login

---

## 12. Frontend Architecture

```
App.jsx
└─ AuthProvider (AuthContext)
   ├─ user state from localStorage
   ├─ SSE session stream (fetch, auth header, auto-reconnect)
   └─ Routes (React Router v6)
      ├─ /login          Login.jsx
      │                  └─ reason banner (expired / superseded)
      ├─ /               Dashboard.jsx (provider patient list)
      ├─ /patient/:id    PatientHistory.jsx (encounter list + badges)
      ├─ /encounter/:id  Workspace.jsx (main AI scribe interface)
      └─ /admin          AdminDashboard.jsx (admin all-patients grid)
```

**State management**: component-local `useState`/`useRef`; no Redux/Zustand. Auth context is the only global state. All API calls via axios with a single interceptor that handles 401/403 centrally.

**PrivateRoute** checks both the React `user` state *and* `localStorage.getItem('token')` so a stale user object doesn't serve a blank page after the token is cleared by the interceptor.
