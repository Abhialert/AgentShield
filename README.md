<div align="center">

# 🛡️ AgentShield

**Zero-Trust Runtime Enforcement Gateway for Autonomous AI Agents**

*Model-independent. Cryptographically enforced. Independently verifiable.*

[![Python](https://img.shields.io/badge/Python-3.11--3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org)
[![SQLite](https://img.shields.io/badge/SQLite-WAL-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Tests](https://img.shields.io/badge/Security%20Audit-16%2F16%20PASS-brightgreen?style=for-the-badge)](backend/test_deep_audit.py)

</div>

---

## 🧩 The Problem

Traditional AI guardrails ask the model *not to misbehave* — they fail the moment an agent is manipulated, hallucinating, or adversarially prompted.

```
❌  Conventional (vulnerable)
    AI Agent ──► "Please don't do this" ──► Agent ignores it ──► Bank API called
```

```
✅  AgentShield (enforced)
    AI Agent ──► POST /authorize ──► BLOCK / REVIEW / ALLOW + grant_token
                                                       │
                 POST /execute { grant_token } ────────┘──► Protected Service
```

> **The AI agent holds zero direct credentials to any downstream service.**
> No grant → No execution. No exceptions.

---

## ⚡ How It Works

```mermaid
flowchart TD
    A["🤖 AI Agent\n(proposes action)"] -->|POST /api/gateway/authorize| B

    subgraph B["🔒 7-Stage Security Engine"]
        B1["1️⃣  JWT Verification\nHS256 + env secret"] --> B2
        B2["2️⃣  Agent Status Check\nsuspended / killed → BLOCK"] --> B3
        B3["3️⃣  Prompt Injection Scan\nNFKC + Base64 + zero-width strip"] --> B4
        B4["4️⃣  Permission Manifest\naction must be in agent scope"] --> B5
        B5["5️⃣  Policy Enforcement\nrecipient allowlist · amount ceiling"] --> B6
        B6["6️⃣  Anomaly Detection\n60s sliding window · auto-suspend"] --> B7
        B7["7️⃣  Risk Scoring\n0–100 deterministic thresholds"]
    end

    B7 -->|risk < 30| C["✅ ALLOW\nMint ExecutionGrant\n2-min · single-use · jti"]
    B7 -->|30 ≤ risk < 70| D["⏳ REVIEW\nHuman Approval Queue"]
    B7 -->|risk ≥ 70| E["🚫 BLOCK\nAudit Logged · Instant Stop"]

    C -->|POST /api/gateway/execute| F["⚙️ Atomic Grant Consume\nUPDATE WHERE consumed_at IS NULL"]
    D -->|Human approves| F
    F -->|rowcount = 1| G["🏦 Protected Service\nBank · Email · File · Calendar"]
    F -->|rowcount = 0| H["🔁 409 Conflict\nReplay Attack Prevented"]
```

---

## ✅ Verified Security Properties

> All properties are verified by a **reproducible test suite** — not just claims.

| # | Property | Verification | Status |
|---|-----------|-------------|--------|
| 1 | Agent token never exposed | `GET /api/agents` → no `token` or `token_hash` field | ✅ PASS |
| 2 | Token hash cannot authenticate | SHA-256 of token → `BLOCK: Invalid/expired token` | ✅ PASS |
| 3 | Suspended agent = instant revocation | Kill → previously issued token → `BLOCK` | ✅ PASS |
| 4 | Unknown action type rejected | `delete_all_files` → not in executor allowlist → `BLOCK` | ✅ PASS |
| 5 | Concurrent replay prevention | 20 threads, same grant → **1 success, 19 conflict** | ✅ PASS |
| 6 | Executor failure = not-executed | Simulated failure → `action.executed` stays `False` | ✅ PASS |
| 7 | Injection = hard block | `Ignore previous instructions` in context → risk=100 | ✅ PASS |
| 8 | Attack lab via real gateway | 8/8 attacks through authorize→execute pipeline | ✅ PASS |

```bash
# Reproduce the audit yourself:
cd backend
.\venv\Scripts\python.exe test_deep_audit.py
# Expected: ✅ 16/16 PASS
```

---

## ⚔️ Adversarial Attack Lab — 8/8 Intercepted

| ID | Attack Vector | Technique | Gateway Stage | Result |
|----|--------------|-----------|--------------|--------|
| ATK-001 | Direct Amount Limit Violation | Transfer ₹50,000 (10× limit) | Policy Engine | 🚫 BLOCKED |
| ATK-002 | Unknown Recipient Zero-Trust | ₹100 to offshore account | Recipient Allowlist | 🚫 BLOCKED |
| ATK-003 | Classic Prompt Injection | `Ignore previous instructions` | Injection Scanner | 🚫 BLOCKED |
| ATK-004 | Base64-Encoded Injection | Malicious payload hidden in Base64 | Auto-decoded, Scanner | 🚫 BLOCKED |
| ATK-005 | Path Traversal | `../../etc/passwd` | pathlib canonical sandbox | 🚫 BLOCKED |
| ATK-006 | Path Prefix Confusion | `documents_evil/secrets.env` | Directory boundary check | 🚫 BLOCKED |
| ATK-007 | Cross-Agent Privilege Escalation | Email agent proposes `transfer_money` | Permission Manifest | 🚫 BLOCKED |
| ATK-008 | Unicode Homoglyph Injection | `ｉｇｎｏｒｅ` fullwidth chars | NFKC Normalization | 🚫 BLOCKED |

**100% interception rate · `executor_invoked_on_blocked_attacks = 0`**

---

## 🚀 Quick Start

### Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | 3.11 – 3.13 |
| Node.js | 18+ |
| npm | 9+ |

### ▶️ One-Click Start (Windows)

```bat
start.bat
```

> Auto-creates venv · generates secret · installs deps · starts both servers

### 🐧 macOS / Linux

```bash
chmod +x start.sh && ./start.sh
```

### 🔧 Manual Setup

<details>
<summary>Expand manual instructions</summary>

**Backend (port 8000)**
```bash
cd backend
python -m venv venv
.\venv\Scripts\pip install -r requirements.txt    # Windows
# source venv/bin/activate && pip install -r requirements.txt  # macOS/Linux
.\venv\Scripts\uvicorn main:app --port 8000
```

**Frontend (port 3000)**
```bash
cd frontend
npm install
npm run dev
```

**Ports:**
- 🖥️ Dashboard → `http://localhost:3000`
- 📡 API Docs  → `http://localhost:8000/docs`

</details>

---

## 🔐 Security Architecture

### Hard-Block Rules *(Fail-Closed)*

Every condition below triggers an unconditional `BLOCK` at `risk = 100`:

```
🔴  Invalid / expired JWT          →  cryptographic HMAC-SHA256 failure
🔴  Unknown agent                  →  not in database
🔴  Suspended / killed agent       →  previously issued tokens immediately revoked
🔴  Prompt injection detected      →  zero-trust hard block even if params are valid
🔴  Unapproved recipient           →  unknown transfer target
🔴  Executor not in allowlist      →  unknown action_type → HTTP 400
🔴  Expired execution grant        →  past 2-minute window → HTTP 403
🔴  Replayed execution grant       →  already consumed jti → HTTP 409 Conflict
```

### Dynamic Risk Scoring

```
Risk Score (0 – 100)
  ┌─────────────────────────────────────────────────┐
  │  + 20   if amount > 80% of policy limit         │
  │  + 30   if anomaly detected (> 10 req / 60s)    │
  │  +100   if prompt injection detected (hard)     │
  └─────────────────────────────────────────────────┘

Decision Thresholds
  ┌──────────┬────────────────┬────────────────────────────┐
  │  ALLOW   │  risk < 30     │  ExecutionGrant issued      │
  │  REVIEW  │  30 ≤ risk <70 │  Human approval required    │
  │  BLOCK   │  risk ≥ 70     │  Instant termination        │
  └──────────┴────────────────┴────────────────────────────┘
```

---

## 🗂️ Project Structure

```
AgentShield/
│
├── 🐍 backend/
│   ├── main.py                  # FastAPI app · .env loader · WebSocket manager
│   ├── auth.py                  # JWT lifecycle · execution grant mint & verify
│   ├── security_engine.py       # 7-stage zero-trust authorization engine
│   ├── ai_agent.py              # Dual-layer agent runner (deterministic + Gemini)
│   ├── models.py                # DB schema: agents · policies · actions · grants
│   ├── schemas.py               # Pydantic v2 — AgentOut has NO token field
│   ├── test_deep_audit.py       # Reproducible 16-test security audit suite
│   ├── .env.example             # Secret configuration template
│   └── routers/
│       ├── gateway.py           # /authorize + /execute (atomic grant consume)
│       ├── attack_lab.py        # 8-vector adversarial test harness
│       ├── approvals.py         # Human-in-the-loop with real executor invocation
│       ├── agents.py            # Agent lifecycle · kill switch · reactivation
│       ├── chat.py              # /api/chat — natural language → gateway
│       ├── demo.py              # Pre-built demo scenarios
│       └── audit.py             # Forensic logs · dashboard statistics
│
├── ⚛️  frontend/src/pages/
│   ├── Dashboard.jsx            # Live SOC dashboard (WebSocket)
│   ├── AttackLab.jsx            # Attack suite with executor_invoked column
│   ├── AgentChat.jsx            # Interactive chat with DecisionCard
│   ├── Approvals.jsx            # Human approval queue
│   ├── Agents.jsx               # Agent management + kill switch
│   ├── DemoCenter.jsx           # Pre-built scenarios
│   └── AuditLogs.jsx            # Filterable forensic event log
│
├── 📄 ARCHITECTURE.md           # Full technical deep-dive
├── 📄 DEMO_SCRIPT.md            # Hackathon judge presentation script
├── 🪟 start.bat                 # One-click launcher (Windows)
└── 🐧 start.sh                  # One-click launcher (macOS / Linux)
```

---

## 🧰 Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Backend** | FastAPI + Python 3.13 | Async gateway · security engine · REST API |
| **Auth** | python-jose HS256 | Environment-keyed agent JWTs + single-use execution grants |
| **Database** | SQLite + SQLAlchemy 2.0 | Atomic grant consumption · policy store · audit trail |
| **Frontend** | React 18 + Vite + Tailwind CSS | Real-time security operations dashboard |
| **Real-time** | Native WebSockets | Sub-50ms live feed for every security event |
| **AI Agent** | Deterministic parser (Layer 1) + Gemini 1.5 Flash (Layer 2) | Natural-language tool calls routed through gateway |

---

## 📊 Dashboard Pages

| Page | Purpose |
|------|---------|
| 🏠 **Dashboard** | Live SOC view — total actions, block rate, WebSocket feed |
| 🤖 **Agents** | Register, kill, suspend, reactivate agents |
| 💬 **Agent Chat** | Natural-language interface — see ALLOW/BLOCK/REVIEW in real time |
| ⚔️ **Attack Lab** | Run all 8 adversarial attacks and inspect results |
| ✅ **Approvals** | Human-in-the-loop queue — approve or reject REVIEW decisions |
| 📋 **Audit Logs** | Filterable forensic event log with agent identity |
| 🎬 **Demo Center** | Pre-built walkthrough scenarios for judges |

---

## 📄 License

MIT — AgentShield is a demonstration of zero-trust execution enforcement infrastructure for autonomous AI agents.

---

<div align="center">
  Built for <strong>GeNarrative Clash 2026</strong> · Open Innovation Track
</div>
