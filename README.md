# Kyron Medical — AI Clinical Scribe Platform

A provider-facing AI clinical documentation platform. A clinician pastes a raw encounter
transcript (or types freeform observations); the system streams back a structured **SOAP
note** (Subjective, Objective, Assessment, Plan) with semantically-matched **ICD-10 codes**,
in real time. Every save is versioned and immutable, prior patient history is injected into
generation through a server-side tool call, and the whole stack runs behind nginx + HTTPS on
AWS EC2 with a private RDS database and all secrets in AWS Secrets Manager.

**Live:** https://scribe.lambdapen.com

---

## Table of contents
1. [Architecture overview](#1-architecture-overview)
2. [Why these technologies](#2-why-these-technologies)
3. [What the platform does](#3-what-the-platform-does)
4. [Data model](#4-data-model)
5. [Key request flows](#5-key-request-flows)
6. [Real-time mechanisms](#6-real-time-mechanisms)
7. [Edge cases & clinical safety](#7-edge-cases--clinical-safety)
8. [Security & infrastructure](#8-security--infrastructure)
9. [Project layout](#9-project-layout)
10. [Testing & verification](#10-testing--verification)
11. [Demo accounts & scenarios](#11-demo-accounts--scenarios)
12. [Sample inputs for verifying templates](#12-sample-inputs-for-verifying-templates)

---

## 1. Architecture overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│  CLIENT — React 18 + Vite SPA (static files)                               │
│  Login · Encounter Workspace · Admin Dashboard · Patient History           │
│  Streaming SOAP renderer · draft autosave · live input validation          │
└───────────────┬────────────────────────────────────────────────────────────┘
                │ HTTPS (TLS, Let's Encrypt)
┌───────────────▼────────────────────────────────────────────────────────────┐
│  EDGE — nginx reverse proxy (80 → 443 redirect, 443 TLS)                    │
│  Serves static dist · proxies /api/ → 127.0.0.1:8000                        │
│  Security headers (HSTS, CSP, …) · login rate-limit · SSE-aware buffering   │
└───────────────┬────────────────────────────────────────────────────────────┘
                │ localhost only — app is never exposed on 80/443 directly
┌───────────────▼────────────────────────────────────────────────────────────┐
│  APPLICATION — FastAPI / uvicorn (127.0.0.1:8000, systemd)                  │
│  Routers: auth · encounters · drafts · admin · icd10                        │
│  Services: ai (SOAP streaming + validation) · icd10_embeddings (vectors)    │
│  JWT auth dependency · single-session enforcement · in-memory SSE event bus │
└───────┬─────────────────────────────────┬──────────────────────────────────┘
        │ psycopg2 (SSL, pooled)           │ HTTPS
┌───────▼──────────────────────┐  ┌────────▼─────────────────────────────────┐
│  DATA — AWS RDS PostgreSQL    │  │  EXTERNAL — Anthropic Claude              │
│  Private subnet (VPC only)    │  │  SOAP generation (streaming + tool-use)   │
│  SQLAlchemy 2.0 · pooled      │  │  Content validation                       │
│  8 normalized tables + indexes│  └───────────────────────────────────────────┘
└───────────────────────────────┘
        ▲
┌───────┴─────────────────────────────────────────────────────────────────────┐
│  SECRETS — AWS Secrets Manager (scribe/prod): DB creds · API key · JWT secret│
└──────────────────────────────────────────────────────────────────────────────┘
```

**Why this shape.** A single public ingress (nginx) keeps the attack surface small and
lets one place own TLS, headers, and rate-limiting. The application binds to `127.0.0.1`
so it is reachable *only* through nginx — never directly on a public port. RDS lives in a
private subnet so it is reachable *only* from inside the VPC. Secrets are pulled from AWS
Secrets Manager at boot, so no credential ever touches disk or the repo.

---

## 2. Why these technologies

| Layer | Choice | Reason |
|-------|--------|--------|
| Frontend | React 18 + Vite + Tailwind | Fast builds, ~105 KB gzipped bundle. Tailwind delivers the dense, high-trust *clinical-tool* aesthetic rather than a consumer look. |
| Streaming | **Server-Sent Events** (not WebSockets) | Note generation is one-directional (server → client). SSE is simpler, auto-reconnects, needs no upgrade handshake, and proxies cleanly through nginx. WebSockets would add bidirectional complexity we don't need. |
| Backend | FastAPI + uvicorn | Async-native, first-class `StreamingResponse` for SSE, Pydantic request validation, and dependency injection that makes auth a one-line decorator. |
| ORM | SQLAlchemy 2.0 (typed) | Fully parameterized queries (injection-safe), explicit connection pooling, eager-loading to avoid N+1 reads. |
| Database | PostgreSQL on RDS | Durable, relational, and its JSONB columns let note content and embeddings live without extra tables. |
| Auth | JWT (HS256) + bcrypt | Stateless tokens for scale; bcrypt for password storage; a DB-backed `session_version` layers single-active-session control on top of otherwise non-revocable JWTs. |
| AI | Anthropic Claude | Strong clinical reasoning, reliable token streaming, and native **tool-use** — the mechanism that lets patient-history retrieval stay server-side instead of being stuffed into the prompt. |
| Embeddings | fastembed `bge-small-en-v1.5` (ONNX, CPU) | 384-dim semantic vectors in ~60 MB with no GPU/PyTorch. Plain-English symptoms map to the right ICD-10 code by *meaning*, not keywords. |
| Process mgmt | systemd | Auto-restart, boot persistence, journald logs, and a pre-start check that fails fast if Secrets Manager is unreachable. |

---

## 3. What the platform does

**Authentication & roles.** Real login with two roles. *Providers* see and edit only their
own encounters; *Admins* see every provider's encounters, manage the provider roster, and
manage note templates. Passwords are bcrypt-hashed; sessions are JWTs with an 8-hour expiry,
and a `session_version` counter enforces a single active session per account.

**Encounter workspace.** A provider starts an encounter with a patient's name + DOB, pastes
a transcript or types observations, and clicks **Generate**. The SOAP note streams back token
by token — Subjective, Objective, Assessment (with at least one suggested ICD-10 code and
description), and Plan — rendering progressively rather than as a spinner-then-dump. The
provider edits inline and saves.

**Patient history & context injection.** When the patient already has saved notes (matched by
first name + last name + DOB), generation pulls their prior encounters **through a backend
tool call** (`get_patient_history`) that Claude invokes mid-generation — not by injecting old
notes into the frontend prompt. The model references relevant prior diagnoses and treatments,
so a returning patient produces visibly different output from a first-time patient.

**Versioning & audit.** Every save appends a new immutable row to `note_versions`; prior
versions are never overwritten or deleted. Providers can browse the full version history —
who saved each version and when, an optional short label per version, and a **line-by-line
diff** between any two versions. Each version also stores a snapshot of the transcript that
produced it, so a note is fully self-contained and reproducible. Logins, saves, template
edits, and version *views* are all recorded in an audit log.

**ICD-10 search.** A standalone widget in the workspace: the provider types a symptom in plain
English and gets the top semantically-relevant ICD-10 codes via local vector similarity over a
300-code embedded reference set (no external ICD-10 API). One click appends a code to the
Assessment section.

**Admin dashboard.** Admin-only: view all encounters filterable by provider and date range;
add and deactivate provider accounts; and full CRUD on **note templates** (structured prompt
fragments that shape generation for different encounter types — e.g. orthopedic follow-up vs.
urgent care). Because the active template is read fresh from the database on each generation,
an admin's template edit takes effect on the provider's *next* Generate with no page refresh.

**Session persistence.** Drafts (transcript + in-progress SOAP + label) autosave to RDS as the
provider types. Refreshing, closing the browser, or logging in from a different device restores
the exact in-progress state — because the draft lives in the database, not in localStorage.

**Input safety.** Non-clinical or garbage input is caught before it can become a hallucinated
note (see [§7](#7-edge-cases--clinical-safety)).

---

## 4. Data model

```
providers ──1:N── encounters ──1:1── notes ──1:N── note_versions
    │                  │                                  │
    │                  ├──N:1── patients                  └── saved_by → providers
    │                  ├──N:1── templates (nullable)
    │                  └──1:1── drafts
    └──1:N── audit_log

icd10_codes  (standalone reference table; code = PK, JSONB embedding)
```

| Table | Purpose | Notable design |
|-------|---------|----------------|
| `providers` | Login identity + role | role enum, `is_active`, `session_version`, bcrypt hash, unique email |
| `patients` | Patient identity | **unique (first, last, dob)** — the natural key used to match returning patients |
| `encounters` | One visit | FKs to patient/provider/template; status enum; `raw_input` transcript; indexed on `provider_id`, `patient_id`, and `(provider_id, updated_at)` |
| `notes` | 1:1 wrapper per encounter | thin row; separates "a note exists" from "its versions" |
| `note_versions` | **Append-only** SOAP history | `(note_id, version_no)` indexed; JSONB content (S/O/A/P, ICD-10, label, transcript snapshot); `saved_by` + `saved_at` |
| `drafts` | In-progress autosave | 1:1 with encounter; JSONB content; deleted on final save |
| `icd10_codes` | 300-code reference | `code` PK; JSONB 384-float embedding; self-contained |
| `audit_log` | Who-did-what | actor, action, target, JSONB extra; logins/saves/template edits/views |

**Why it's normalized this way.** Splitting `notes` from `note_versions` lets each prior
version stay immutable while a new row is appended — version data depends only on the version
key (3NF). Factoring patient identity out of encounters means one patient row is shared across
all their visits, which is exactly what the returning-patient matching relies on.

---

## 5. Key request flows

**Generate a SOAP note**
```
POST /api/encounters/generate (transcript, encounter_id, template_id)
  → fast pre-filter for obviously empty/non-clinical input (no API spend)
  → system prompt = base + the active template's prompt fragment
  → call Claude with the get_patient_history tool available
  → Claude calls the tool → server runs a DB query → returns prior Dx/Tx or "first-time"
  → Claude streams SOAP JSON; each token is forwarded as an SSE event
  → frontend parses partial JSON live and fills S/O/A/P as it arrives
```

**Save (versioned)**
```
POST /api/encounters/save
  → server-side AI validation of transcript + SOAP (reject garbage)
  → append note_versions(version_no = count + 1, content JSONB, saved_by, saved_at)
  → status = saved; draft deleted; audit_log row written
```

**ICD-10 search**
```
GET /api/icd10/search?q=...
  → embed query (bge-small) → cosine similarity vs 300 stored vectors → top-k
```

**Draft autosave / restore**
```
edit  → PUT /api/drafts (debounced) → upsert drafts.content JSONB
open  → GET /api/encounters/{id} → restore transcript + SOAP + label
```

---

## 6. Real-time mechanisms

Three independent live paths, each chosen for its job:

| Mechanism | Transport | Purpose |
|-----------|-----------|---------|
| SOAP generation | SSE (`/encounters/generate`) | progressive token-by-token rendering |
| Session supersession | SSE (`/auth/session-stream`) | when the same account logs in elsewhere, push `flush` (save draft) then `superseded` (lock the old tab) |
| Live input validation | debounced POST (`/encounters/validate-content`) | ~1.4 s after typing stops, classify input as clinical vs garbage; drives the warning banner and Save button |

> **On the one in-memory structure (and why it does not violate "all data in RDS").**
> The session bus holds only a registry of *currently-open SSE connections* (`asyncio`
> queues) plus the transient `flush` / `superseded` signals pushed through them. This is
> ephemeral connection state — the same category as a live TCP socket or WebSocket handle —
> **not** persistent data. It contains none of the business entities (encounters, note
> versions, patients, providers, templates, audit logs all live in RDS), and nothing in it
> needs to survive a restart: if the process restarts the SSE connections drop at the network
> layer anyway, clients reconnect, and they re-register. The durable thing behind session
> persistence — the in-progress **draft** — is saved to the RDS `drafts` table; the bus only
> fires the real-time "save now" nudge. Because the registry is per-process the app runs a
> single worker; isolating it in `session_events.py` means swapping in Redis pub/sub is the
> only change required to scale horizontally.

---

## 7. Edge cases & clinical safety

**Non-clinical / garbage input never becomes a hallucinated note.** Bad input is stopped by
four independent gates: (1) instant heuristics for empty input and numeric spam; (2) an AI
quality gate in the generation prompt that returns a fixed "insufficient content" response
instead of inventing a note; (3) a live, as-you-type AI validator that catches keyboard-mash
words heuristics can't see; and (4) a server-side re-validation on save so nothing slips
through even if the UI is bypassed. The validator is tuned conservative — real English such as
"no medication needed" passes; only genuine random strings are flagged.

**Session expired / superseded — no data loss.** A second login first tells the old tab over
SSE to flush its draft *while its token is still valid*, waits a grace period, then increments
`session_version` (invalidating the old JWT) and signals `superseded`. The old tab locks with a
"logged in elsewhere" overlay, and its work is already saved.

**Provider deactivated mid-draft — clean lockout.** Setting `is_active = False` makes the next
authenticated request return 403. The draft already lives in RDS, so nothing is lost and the
provider sees a deactivated state instead of an error.

---

## 8. Security & infrastructure

| Control | Implementation |
|---------|----------------|
| Secrets | AWS Secrets Manager (`scribe/prod`), loaded at boot — no `.env`, no hardcoded credentials |
| RDS isolation | private VPC subnet, not publicly accessible; `sslmode=require` |
| Transport | HTTPS via Let's Encrypt (valid cert, 80 → 443 redirect); HSTS 1-year |
| Reverse proxy | nginx is the only public listener; app bound to `127.0.0.1:8000` |
| Headers | CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy |
| AuthN / AuthZ | bcrypt + JWT; per-request ownership checks; admin-only route gate |
| Session control | `session_version` enforces one active session per account |
| Brute force | nginx login rate-limit (5/min, burst 3) |
| Injection | SQLAlchemy parameterized queries throughout |
| Connection pooling | engine pool (size 10 / overflow 20, pre-ping, recycle 3600) — never one connection per request |

---

## 9. Project layout

```
scribe/
├── backend/
│   ├── main.py                 FastAPI app, CORS, static SPA serving, /api/health
│   ├── config.py               Secrets Manager loader + typed settings
│   ├── database.py             SQLAlchemy engine, pool, session factory
│   ├── auth.py                 bcrypt, JWT, current-provider dependency, admin gate
│   ├── models.py               8 ORM models (normalized schema + indexes)
│   ├── session_events.py       in-memory SSE event bus
│   ├── routers/
│   │   ├── auth.py             login, /me, session-stream (SSE)
│   │   ├── encounters.py       create / generate (SSE) / save / list / validate-content
│   │   ├── drafts.py           draft upsert + fetch
│   │   ├── admin.py            providers, templates, all-encounters, version-views
│   │   └── icd10.py            semantic search
│   ├── services/
│   │   ├── ai.py               SOAP streaming, tool-use, validation, ICD-10 search
│   │   └── icd10_embeddings.py ONNX embedding model + cosine similarity
│   ├── seed_demo.py            demo providers, patients, encounters, templates
│   └── seed_icd10.py           300-code ICD-10 set + embeddings
└── frontend/
    └── src/pages/              Login, Workspace, AdminDashboard, PatientHistory, Dashboard
```

---

## 10. Testing & verification

### 10.1 Infrastructure checks
```bash
# App health + live DB connectivity
curl -s https://scribe.lambdapen.com/api/health
# → {"status":"ok","db":"connected"}

# TLS is valid (not self-signed) and HTTP redirects to HTTPS
curl -sI http://scribe.lambdapen.com        # → 301 to https
curl -sI https://scribe.lambdapen.com        # → 200, HSTS header present

# App is NOT directly exposed — only nginx is public
#   (port 8000 is bound to 127.0.0.1; only 80/443 are open)

# RDS is private — its endpoint resolves to a 172.31.x.x VPC address
#   and is not reachable from outside the VPC
```

### 10.2 Core workflow (manual, per role)
1. **Login** as a provider → only that provider's encounters are visible.
2. **Generate** → paste a transcript, click Generate, confirm the SOAP note streams in
   progressively and includes S/O/A/P plus at least one ICD-10 code.
3. **ICD-10 search** → type a plain-English symptom, append a result to the Assessment.
4. **Edit & save** → edit inline, save, reopen, confirm a new version was created and the
   prior version is intact; open the **diff** between versions.
5. **Returning patient** → generate for a patient who already has notes; confirm the output
   references prior diagnoses/treatments (and that history came from the backend tool call,
   visible in the server logs).
6. **Session persistence** → refresh mid-draft; confirm the transcript + SOAP restore. Log in
   from a second browser; confirm the first tab flushes its draft and shows "superseded".
7. **Admin** → view all encounters, filter by provider/date; edit a template, then regenerate
   as the provider and confirm the output changes with no page refresh; add and deactivate a
   provider.

### 10.3 Edge cases
- **Garbage input:** paste keyboard-mash or numeric spam → the live validator flags it, Save is
  disabled, and Generate returns a graceful "insufficient content" response rather than a
  fabricated note. Confirm the server-side save guard also rejects it (HTTP 422) if forced.
- **Deactivated provider:** while a provider has a draft open, deactivate them from the admin
  dashboard → their next action is rejected cleanly and the draft remains in the database.

### 10.4 Backend validation harness
The AI content validator is verified directly against representative inputs — valid clinical
text and short legitimate phrases pass; appended keyboard-mash and random strings are rejected
— so the conservative tuning (real English passes, only true gibberish fails) is confirmed
before relying on it in the UI.

---

## 11. Demo accounts & scenarios

Demo credentials are seeded for review. Every provider sees only their **own**
encounters; the admin sees all of them — so the same patient under two providers is a
natural way to show data isolation.

| Account | Password | Role / specialty | What it's best for demonstrating |
|---------|----------|------------------|----------------------------------|
| `admin@kyron.health` | `Admin1234!` | Admin (Alex Morgan) | Cross-provider oversight: all-encounters view with provider/date filters, add/deactivate providers, template CRUD with live effect, version-view audit |
| `sarah.chen@kyron.health` | `Provider1234!` | Provider — Internal Medicine | The richest dataset: returning patients, multi-version history, diff view, version labels, an open draft |
| `james.rivera@kyron.health` | `Provider1234!` | Provider — Orthopedics | Template-shaped output (Orthopedic Follow-Up), a returning post-op patient |
| `emily.patel@kyron.health` | `Provider1234!` | Provider — Urgent Care | New-patient evaluation, in-progress drafts (session persistence), provider isolation |
| `m.torres@kyron.health` | *(deactivated)* | Provider — deactivated | The deactivated-account state in the roster; deactivated users cannot log in |

### Per-account walkthroughs

**Admin — Alex Morgan**
- Admin Dashboard → encounters from *all* providers; filter by provider and by date range.
- Provider roster → add a provider, deactivate / reactivate one.
- Templates → edit e.g. "Orthopedic Follow-Up"; then, as a provider, regenerate and watch
  the output change **without a page refresh**.
- Version-view audit → who viewed which note version and when.

**Sarah Chen (Internal Medicine) — the core demo provider**
- **Margaret Thompson** (returning, 2 visits): visit 1 has versions *Initial Assessment →
  Medication Adjusted* (open the **diff** to see exactly what changed); visit 2 has *6-Week
  Follow-Up → Goals Achieved*. As a returning patient, a fresh generation pulls her prior
  history through the backend tool call.
- **Robert Kim** (returning): an *Initial Visit*, plus a *10-Week Follow-Up* with **3
  versions and an open draft** — ideal for showing version history, diff, *and* session
  persistence (refresh → the draft restores).

**James Rivera (Orthopedics)**
- **Elena Rodriguez** (returning post-op): *6-Week Post-Op → PT Plan Updated* (2 versions),
  then *12-Week Review*. The **Orthopedic Follow-Up** template visibly shapes the note and
  prior-visit context carries forward.
- **William Foster**: a single **Urgent Care Visit** for contrast.

**Emily Patel (Urgent Care)**
- **David Park**: *Chronic Disease Review → Treatment Stepped Up* (2 versions).
- **Margaret Thompson** and **Robert Kim** also appear here — but Emily sees only *her own*
  encounters for them, which demonstrates **provider isolation** (the admin, by contrast,
  sees everyone's).
- Open drafts (an urgent-care draft, a Robert Kim draft) → **session persistence**: refresh
  or log in from another browser and the in-progress work restores exactly.

**Michael Torres (deactivated)**
- Shows as **inactive** in the admin roster; login is rejected. To demonstrate the *live*
  lockout, deactivate an active provider (e.g. Emily) from the admin dashboard while she has
  a draft open — her next action is cleanly rejected and her draft is preserved.

### Non-happy-path inputs (any provider)
- Paste keyboard-mash or numeric spam into the transcript → the live validator flags it,
  **Save** is disabled, and **Generate** returns a graceful "insufficient content" response
  instead of a fabricated note.

---

## 12. Sample inputs for verifying templates

To prove the template engine actually shapes generation, use a template with a few
*visually unmistakable* instructions and a transcript that gives it material to work with.
Generate the same transcript under the **General** template and under this one — the
difference is obvious.

### Template — create via Admin → Templates

**Name:** `Cardiology Consult`

**System prompt:**
```
You are a board-certified cardiologist writing a consult note. Follow this exact structure and formatting so the note is instantly recognizable as a cardiology consult:

- Begin the note with a single line starting "⚠ CANNOT-MISS:" listing the emergent cardiac diagnoses you actively ruled in or out (e.g. ACS, aortic dissection, PE, pericardial tamponade).
- Subjective: Cardiac-focused HPI — chest pain character (pressure/sharp/tearing), radiation, exertional vs rest, associated dyspnea/diaphoresis/syncope, and cardiac risk factors (HTN, DM, smoking, hyperlipidemia, family history of premature CAD).
- Objective: Vitals including BP in both arms if dissection is considered. Cardiovascular and pulmonary exam. Report ECG interpretation and any cardiac biomarkers.
- Assessment: State a cardiac risk stratification (give a HEART score with its component breakdown) and the primary cardiac diagnosis with reasoning.
- Plan: Write the Plan as an explicitly NUMBERED list (1., 2., 3. …) of ordered actions covering diagnostics, medications with cardiac dosing, monitoring, and disposition (admit/observe/discharge).
- End with a section titled "PATIENT-FRIENDLY SUMMARY:" — 2-3 sentences in plain, non-technical language a patient could understand.

Use precise cardiology terminology in the clinical sections, but keep the patient summary jargon-free.
```

### Matching test transcripts — paste into the workspace (input only)

Two different cardiac presentations for the **same** Cardiology Consult template. Generate
each in turn (same encounter, just swap the transcript and regenerate) — the template stays
constant but the output changes completely, proving generation is driven by the live input.

**Transcript A — exertional chest pain (ACS workup):**
```
58-year-old male, intermittent chest tightness for 3 days, worse climbing stairs, partially relieved by rest. Pressure-like, central chest, radiated to the left arm once yesterday. Mild shortness of breath and sweating during episodes. No syncope or palpitations. History of hypertension and type 2 diabetes, both on medication. Father had a heart attack at 60. Former smoker, quit 5 years ago, 20 pack-year history. BP 148/92 in the right arm, 150/90 in the left arm. Heart rate 88, regular. Lungs clear. ECG shows nonspecific ST-T changes, no acute ST elevation. First troponin pending.
```

**Transcript B — palpitations (new atrial fibrillation):**
```
67-year-old woman with sudden-onset palpitations and lightheadedness for the past 6 hours. Describes a racing, irregular heartbeat at rest, no chest pain, mild shortness of breath on exertion. No syncope. History of hypertension and mild heart failure. Not on any blood thinner. Pulse is irregularly irregular at about 130. BP 132/84. No leg swelling, lungs have mild bibasilar crackles. ECG shows atrial fibrillation with rapid ventricular response, no ST elevation. Thyroid function pending.
```

Under the same template, A drives an ACS workup (HEART score, troponin, dual antiplatelet
discussion) while B drives an atrial-fibrillation plan (CHA₂DS₂-VASc score, rate vs rhythm
control, anticoagulation) — same structure, entirely different clinical content.

### What proves the template worked

With **Cardiology Consult** active, the generated note shows four markers that the General
template does **not** produce:
1. An opening **`⚠ CANNOT-MISS:`** line of emergent diagnoses ruled in/out.
2. A **HEART score** risk stratification with its component breakdown in the Assessment.
3. A **numbered** Plan list (1., 2., 3. …) rather than prose.
4. A closing **`PATIENT-FRIENDLY SUMMARY:`** written in plain language.

### Edge cases this also exercises
- **New template appears immediately (no refresh):** create the template as admin, then —
  without reloading — open the provider's template picker on a new encounter; it's already
  there. (Templates are read fresh from the DB at picker-open and at generation time.)
- **Same encounter, different input → different output:** in one encounter, generate the
  cardiac transcript, then change the transcript (or switch the template) and regenerate —
  the output changes, proving nothing is cached.
- **Reactivate a deactivated account:** Admin → roster → Activate a deactivated provider;
  their login, previously rejected, now succeeds (`is_active` flips, auth stops returning 403).

---

*Built on AWS EC2 + RDS. FastAPI · React · PostgreSQL · Anthropic Claude.*
