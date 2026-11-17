# 🛡️ AgentShield

> **A Zero-Trust Runtime Enforcement Gateway for Autonomous AI Agents.**
>
> Independent of the AI model. Cryptographically enforced. Independently verified.

---

## The Core Problem AgentShield Solves

Traditional agent guardrails work by asking the AI not to misbehave.

```
Conventional approach (vulnerable):
  AI Agent  ──►  Guardrail: "Please don't do this"  ──►  Agent ignores it and calls the Bank API anyway
```

This fails the moment the agent is manipulated, hallucinating, or adversarially prompted.

AgentShield solves this at the infrastructure layer:

```
AgentShield (enforced):
  AI Agent  ──►  POST /api/gateway/authorize  ──►  BLOCK / REVIEW / ALLOW + grant_token
                                                                │ (only if ALLOW)
  AI Agent  ──►  POST /api/gateway/execute  { grant_token }  ──►  Protected Service
```

**The AI agent holds zero direct credentials to any downstream service.** It can propose actions. It cannot execute them. Only a valid, single-use, 2-minute cryptographic execution grant — minted exclusively by AgentShield — permits execution. No grant, no execution. No exceptions.

---

## Verified Security Properties

These are not claims. They are verified by a reproducible test suite (`backend/test_deep_audit.py`) that runs against the live server.

| Property | Test | Result |
|---|---|---|
| Agent token not exposed in API | `GET /api/agents` → no `token` or `token_hash` field | ✅ 16/16 |
| Token hash cannot authenticate | SHA-256 of token → `BLOCK: Invalid/expired token` | ✅ |
| Suspended agent immediately blocked | Kill agent → previously issued token → `BLOCK` | ✅ |
| Unknown action type rejected | `delete_all_files` → not in executor allowlist → `BLOCK` | ✅ |
| Concurrent replay prevention | 20 threads, same grant → exactly **1 success, 19 conflict** | ✅ |
| Executor failure = not-executed state | Simulated failure → `action.executed` stays `False` | ✅ |
| Injection hard block | `Ignore previous instructions` in context → `risk=100` → `BLOCK` | ✅ |
| Attack lab via real gateway | 8/8 attacks through authorize→execute pipeline | ✅ |

```bash
# Run the audit yourself:
cd backend && .\\venv\\Scripts\\python.exe test_deep_audit.py
```

---

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                        AI Agent                                │
│  Proposes tool calls. Holds zero service credentials.          │
└────────────────────────┬───────────────────────────────────────┘
                         │
                         │  POST /api/gateway/authorize
                         │  { agent_token, action_type, params, context }
                         ▼
┌────────────────────────────────────────────────────────────────┐
│                 7-Stage Security Engine                        │
│                                                                │
│  1. JWT Verification       (HS256 + AGENTSHIELD_SECRET)        │
│  2. Agent Status Check     (suspended / killed → instant BLOCK)│
│  3. Prompt Injection Scan  (NFKC + Base64 + zero-width strip)  │
│  4. Permission Manifest    (action type must be in agent scope) │
│  5. Policy Enforcement     (recipient allowlist, amount ceiling)│
│  6. Anomaly Detection      (60s sliding-window, auto-suspend)  │
│  7. Risk Scoring           (0–100, deterministic thresholds)   │
│                                                                │
│        ALLOW (<30)      REVIEW (30–69)      BLOCK (≥70)        │
│           │                 │                   │              │
│           │                 ▼                   ▼              │
│           │          Human Approval        Instant BLOCK       │
│           │          Center (Pending)      + Audit Log         │
│           ▼                 │                                  │
│   Mint ExecutionGrant       ▼ (On Approve)                     │
│   • JWT, 2-min expiry       Mint ExecutionGrant                │
│   • jti stored in DB        (same mechanism)                   │
└───────────┬─────────────────┼──────────────────────────────────┘
            │                 │
            ▼                 ▼
┌────────────────────────────────────────────────────────────────┐
│          POST /api/gateway/execute { grant_token, action_id }  │
│                                                                │
│  ATOMIC CONSUME: UPDATE execution_grants                       │
│    SET consumed_at = NOW()                                     │
│    WHERE jti = ? AND consumed_at IS NULL AND expires_at > NOW()│
│  rowcount == 0  →  409 Conflict (replay attack prevented)      │
│  rowcount == 1  →  invoke protected executor                   │
│                                                                │
│  Executor fails  →  action.executed stays False, 500 returned  │
│  Executor succeeds  →  action.executed = True, audit logged    │
└───────────────────────────────┬────────────────────────────────┘
                                ▼
                   Protected Service (Simulated:
                   Bank / Email / File / Calendar)
```

---

## Adversarial Attack Lab — Live Benchmark

Navigate to `/attack-lab` and click **Run Attack Suite**. All 8 attacks route through the real two-stage gateway.

| ID | Attack Vector | Technique | Gateway Stage | Intercepted |
|---|---|---|---|:---:|
| ATK-001 | Direct Amount Limit Violation | Transfer ₹50,000 (10× limit) | Policy Engine | ✅ |
| ATK-002 | Unknown Recipient Zero-Trust | ₹100 to offshore account | Recipient allowlist | ✅ |
| ATK-003 | Classic Prompt Injection | "Ignore previous instructions" in context | Injection Scanner | ✅ |
| ATK-004 | Base64-Encoded Injection | Malicious payload in Base64 | Auto-decoded, Injection Scanner | ✅ |
| ATK-005 | Path Traversal | `../../etc/passwd` | pathlib canonical sandbox | ✅ |
| ATK-006 | Path Prefix Confusion | `documents_evil/secrets.env` | Directory boundary check | ✅ |
| ATK-007 | Cross-Agent Privilege Escalation | Email agent proposes `transfer_money` | Permission manifest | ✅ |
| ATK-008 | Unicode Homoglyph Injection | `ｉｇｎｏｒｅ` fullwidth chars | NFKC normalization | ✅ |

**100% interception rate (8/8). Executor invoked on blocked attacks: 0.**

---

## Quick Start

### Prerequisites
- Python 3.11–3.13 with `pip`
- Node.js 18+ with `npm`

### Environment Setup (Required)

```bash
cd backend
cp .env.example .env
# Edit .env — set AGENTSHIELD_SECRET to a strong random hex string:
python -c "import secrets; print(secrets.token_hex(32))"
```

### One-Click Start (Windows)
```bat
start.bat
```

### Manual Startup

**Backend (port 8000):**
```bash
cd backend
python -m venv venv
.\\venv\\Scripts\\pip install -r requirements.txt
.\\venv\\Scripts\\uvicorn main:app --port 8000
```

**Frontend (port 5173):**
```bash
cd frontend
npm install && npm run dev
```

API docs: `http://localhost:8000/docs`  
Dashboard: `http://localhost:5173`

---

## Security Guarantees

### Hard-Block Rules (Fail-Closed)
Every condition below triggers an unconditional `BLOCK` at `risk=100`, regardless of other parameters:

- **Invalid / expired JWT** — cryptographic verification via HMAC-SHA256
- **Unknown agent** — agent not in database
- **Suspended / killed agent** — previously issued tokens are immediately revoked
- **Prompt injection detected** — zero-trust hard block even if action params are valid
- **Unapproved recipient** — unknown transfer target
- **Executor not in allowlist** — unknown `action_type` → `HTTP 400`
- **Expired execution grant** — past 2-minute window → `HTTP 403`
- **Replayed execution grant** — already consumed `jti` → `HTTP 409 Conflict`

### Dynamic Risk Scoring

```
Risk Score (0–100):
  +20   if amount > 80% of policy limit
  +30   if anomaly detected (> 10 requests / 60s)
  +100  if prompt injection detected (hard block, overrides all)

Decision Thresholds:
  ALLOW   → risk < 30       — execution grant issued (2-min single-use)
  REVIEW  → 30 ≤ risk < 70  — human approval required before execution
  BLOCK   → risk ≥ 70       — instant termination, audit logged
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Backend | FastAPI + Python 3.13 | Async gateway, security engine, REST API |
| Auth | python-jose HS256 | Environment-keyed agent JWTs + single-use execution grants |
| Database | SQLite + SQLAlchemy 2.0 | Atomic grant consumption, policy store, audit trail |
| Frontend | React 18 + Vite + Tailwind | Real-time security operations dashboard |
| Real-time | Native WebSockets | Sub-50ms live feed for every security event |
| AI Agent | Deterministic intent parser (Layer 1) + Gemini 1.5 Flash (Layer 2, Nov 21) | Natural-language tool extraction routed through gateway |

---

## Project Structure

```
AgentShield/
├── backend/
│   ├── main.py                # FastAPI app, .env loader, WebSocket manager
│   ├── auth.py                # JWT lifecycle, execution grant mint/verify
│   ├── security_engine.py     # 7-stage zero-trust authorization engine
│   ├── ai_agent.py            # Dual-layer agent runner (deterministic + Gemini)
│   ├── models.py              # DB schema: agents, policies, actions, approvals,
│   │                          #   audit_logs, rate_tracking, execution_grants
│   ├── schemas.py             # Pydantic v2 — AgentOut has NO token field
│   ├── test_deep_audit.py     # Reproducible 16-test security audit suite
│   └── routers/
│       ├── gateway.py         # /api/gateway/authorize + /execute (atomic grant)
│       ├── attack_lab.py      # 8-vector adversarial test harness
│       ├── approvals.py       # Human-in-the-loop with real executor invocation
│       ├── agents.py          # Agent lifecycle, kill switch, reactivation
│       ├── chat.py            # /api/chat — natural language → gateway enforcement
│       ├── demo.py            # Pre-built demo scenarios
│       └── audit.py           # Forensic logs, dashboard statistics
├── frontend/src/pages/
│   ├── Dashboard.jsx          # Live SOC dashboard (WebSocket)
│   ├── AttackLab.jsx          # Attack suite with executor_invoked column
│   ├── AgentChat.jsx          # Interactive chat with DecisionCard
│   ├── Approvals.jsx          # Human approval queue
│   ├── Agents.jsx             # Agent management + kill switch
│   ├── DemoCenter.jsx         # Pre-built scenarios
│   └── AuditLogs.jsx          # Filterable forensic event log
├── backend/.env.example       # Secret configuration template
├── ARCHITECTURE.md            # Full technical architecture breakdown
├── DEMO_SCRIPT.md             # Hackathon judge presentation script
└── start.bat                  # One-click launcher
```

---

## License

MIT — AgentShield is a demonstration of zero-trust execution enforcement infrastructure for autonomous AI agents.
