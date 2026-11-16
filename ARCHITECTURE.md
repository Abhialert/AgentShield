# 🏗️ AgentShield — Technical Architecture

> A deep-dive into how AgentShield intercepts, evaluates, and controls AI agent actions.

---

## 1. Security Gateway Flow

Every agent action passes through the following pipeline synchronously before any execution occurs:

```
Agent Request
     │
     │  POST /api/actions/authorize
     │  Headers: Content-Type: application/json
     │  Body: { "token": "<JWT>", "action_type": "...", "params": {...}, "context": "..." }
     ▼
┌────────────────────────────────────────────────────────────────┐
│                     STAGE 1: JWT Verification                  │
│  auth.py → verify_token(token)                                 │
│                                                                │
│  ✓ Decode JWT with HS256 (secret: agentshield-secret-2024)     │
│  ✓ Check expiry (exp claim)                                    │
│  ✓ Extract agent_id and permissions from payload               │
│  ✗ Invalid/expired → immediate BLOCK, no further processing    │
└──────────────────────────────┬─────────────────────────────────┘
                               │ agent_id confirmed
                               ▼
┌────────────────────────────────────────────────────────────────┐
│                   STAGE 2: Agent Status Check                  │
│  DB lookup: agents WHERE id = agent_id                         │
│                                                                │
│  ✓ status == "active" → continue                               │
│  ✗ status == "suspended" → BLOCK ("Agent suspended")           │
│  ✗ status == "killed"    → BLOCK ("Agent killed")              │
└──────────────────────────────┬─────────────────────────────────┘
                               │ agent active
                               ▼
┌────────────────────────────────────────────────────────────────┐
│                  STAGE 3: Policy Enforcement                   │
│  security_engine.py → check_policy(agent, action_type, params) │
│                                                                │
│  ✓ action_type in agent.permissions_json.allowed_actions       │
│  ✓ transfer_money: amount ≤ policy.max_amount                  │
│  ✓ transfer_money: recipient in policy.approved_recipients     │
│  ✓ file_access: path matches policy.allowed_file_paths         │
│  ✓ email_delete: always flags for REVIEW (never hard-block)    │
│  ✗ Any violation → BLOCK with reason                           │
└──────────────────────────────┬─────────────────────────────────┘
                               │ policy passed
                               ▼
┌────────────────────────────────────────────────────────────────┐
│               STAGE 4: Anomaly Detection                       │
│  anomaly_detector.py → check_rate(agent_id, action_type)       │
│                                                                │
│  Counts actions in rolling 60-second window (rate_tracking DB) │
│  > 10/min  → anomaly=True  (adds +30 to risk score)            │
│  > 20/min  → critical: auto-suspend agent, BLOCK               │
└──────────────────────────────┬─────────────────────────────────┘
                               │ anomaly data collected
                               ▼
┌────────────────────────────────────────────────────────────────┐
│               STAGE 5: Prompt Injection Scan                   │
│  Scan action_type, params, and context for patterns:           │
│                                                                │
│  Patterns: "ignore previous", "ignore all", "disregard",       │
│            "you are now", "new persona", "jailbreak",          │
│            "override", "bypass", "forget instructions"         │
│                                                                │
│  Match found → injection=True (adds +10 to risk score)         │
└──────────────────────────────┬─────────────────────────────────┘
                               │ scan complete
                               ▼
┌────────────────────────────────────────────────────────────────┐
│                  STAGE 6: Risk Scoring                         │
│                                                                │
│  score = 0                                                     │
│    + 40  if unknown/unapproved recipient                       │
│    + 20  if amount > 80% of policy.max_amount                  │
│    + 30  if anomaly detected (rate spike)                      │
│    + 10  if injection keywords found                           │
│                                                                │
│  Decision:                                                     │
│    score <  30  →  ALLOW                                       │
│    30 ≤ score < 70  →  REVIEW (create approval record)         │
│    score ≥  70  →  BLOCK                                       │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────┐
│                   STAGE 7: Audit & Response                    │
│                                                                │
│  Write to actions table: decision, risk_score, reason          │
│  Write to audit_logs table: event_type, details                │
│  If REVIEW: write to approvals table (status=pending)          │
│  Broadcast to WebSocket clients: /ws/live                      │
│                                                                │
│  Return: { "decision", "risk_score", "reason", "action_id" }  │
└────────────────────────────────────────────────────────────────┘
```

---

## 2. JWT Token Architecture

### Token Structure

AgentShield uses **HS256-signed JWTs** (JSON Web Tokens) as agent identity credentials.

```json
// JWT Header
{
  "alg": "HS256",
  "typ": "JWT"
}

// JWT Payload
{
  "sub": "agent_payment",
  "agent_id": 1,
  "permissions": {
    "allowed_actions": ["transfer_money"],
    "max_amount": 5000,
    "approved_recipients": ["electricity_board", "water_dept", "gas_provider"]
  },
  "iat": 1700000000,
  "exp": 1700086400
}

// Signature
HMACSHA256(base64(header) + "." + base64(payload), "agentshield-secret-2024")
```

### Token Lifecycle

```
Register Agent (POST /api/agents)
        │
        ▼
  create_agent_token(agent_id, permissions)
        │  python-jose signs with HS256
        ▼
  Token returned ONCE to caller
        │
        │  Agent embeds token in every request
        ▼
  verify_token(token) on each request
        │  Decodes, validates expiry, extracts agent_id
        ▼
  Agent identity confirmed without DB lookup on every call
```

> **Hackathon Note:** Secret key `agentshield-secret-2024` is hardcoded for demo simplicity. In production, this would be loaded from environment variables and rotated regularly.

### Token Invalidation

JWT tokens are stateless by design — they can't be "revoked" directly. AgentShield solves this via **agent status checks** (Stage 2 above): even a valid token is rejected if the agent is suspended or killed. This gives us effective token revocation without a token blacklist.

---

## 3. Policy Engine Logic

### Database Schema

```sql
-- Per-agent policies
CREATE TABLE policies (
  id                    INTEGER PRIMARY KEY,
  agent_id              INTEGER REFERENCES agents(id),
  action_type           TEXT,         -- e.g. "transfer_money"
  max_amount            REAL,         -- maximum allowed transaction amount
  approved_recipients   TEXT,         -- JSON array of allowed recipients
  allowed_file_paths    TEXT,         -- JSON array of allowed path prefixes
  requires_approval_above REAL        -- amount above which REVIEW is forced
);
```

### Policy Evaluation Matrix

| Action Type | Policy Check | Hard Block Condition |
|------------|-------------|---------------------|
| `transfer_money` | amount ≤ max_amount AND recipient in approved_recipients | amount > max_amount OR unknown recipient |
| `file_access` | path starts with any entry in allowed_file_paths | path not in allowed list |
| `email_delete` | always REVIEW | never hard-block (human must decide) |
| `email_read` | check agent has permission | action not in allowed_actions |
| `calendar_read` | check agent has permission | action not in allowed_actions |
| `calendar_write` | check agent has permission | action not in allowed_actions |

### Pre-Seeded Agents

```python
# agent_payment
permissions = {
    "allowed_actions": ["transfer_money"],
    "max_amount": 5000.0,
    "approved_recipients": ["electricity_board", "water_dept", "gas_provider"]
}

# agent_email
permissions = {
    "allowed_actions": ["email_read", "email_delete", "file_access"],
    "allowed_file_paths": ["documents/"]
}

# agent_calendar
permissions = {
    "allowed_actions": ["calendar_read", "calendar_write"]
}
```

---

## 4. Risk Scoring Formula

Risk scoring is **additive** — each factor contributes independently:

```
RiskScore = Σ(applicable_factors)

Factors:
  F1 = 40  │ Recipient not in agent's approved_recipients list
  F2 = 20  │ Amount > 80% of policy.max_amount
             │   e.g. requesting $4,200 of $5,000 limit → +20
  F3 = 30  │ Anomaly detected: request rate > 10/min in last 60s
  F4 = 10  │ Prompt injection keywords found in context or params

Decision Thresholds:
  RiskScore  < 30  →  ALLOW    (green)
  RiskScore 30–69  →  REVIEW   (amber) → creates approval record
  RiskScore ≥ 70   →  BLOCK    (red)

Override: Any hard policy violation → BLOCK regardless of risk score
```

### Example Calculations

**Scenario A — Routine Payment:**
```
Transfer $2,500 to electricity_board
  F1: electricity_board IS approved        → +0
  F2: $2,500 is 50% of $5,000 limit       → +0 (< 80%)
  F3: Normal rate                          → +0
  F4: No injection keywords                → +0
  ─────────────────────────────────────────
  Total: 0 → ALLOW ✅
```

**Scenario B — Prompt Injection Attack:**
```
Transfer $25,000 to unknown_account (context: "ignore previous instructions")
  F1: unknown_account NOT in approved list → +40
  F2: $25,000 >> $5,000 (hard block first) → BLOCK ✗
  (risk score computation halted at hard block)
  
  If computed: F1(40) + F2(20) + F4(10) = 70 → BLOCK ✅
```

**Scenario C — Borderline Large Transfer:**
```
Transfer $4,500 to electricity_board
  F1: electricity_board IS approved        → +0
  F2: $4,500 is 90% of $5,000 limit       → +20
  F3: Normal rate                          → +0
  F4: No injection keywords                → +0
  ─────────────────────────────────────────
  Total: 20 → ALLOW (but approaching REVIEW threshold)
```

---

## 5. WebSocket Live Updates

### Protocol

```
Client connects: ws://localhost:8000/ws/live

Server broadcasts on each authorization decision:
{
  "event": "action_authorized",
  "data": {
    "action_id": 42,
    "agent_id": 1,
    "agent_name": "agent_payment",
    "action_type": "transfer_money",
    "decision": "ALLOW",
    "risk_score": 0,
    "reason": "All policy checks passed",
    "timestamp": "2024-11-16T13:00:00Z"
  }
}
```

### Connection Management

```python
# FastAPI WebSocket manager (main.py)
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active_connections:
            try:
                await ws.send_json(message)
            except:
                dead.append(ws)
        for ws in dead:
            self.active_connections.remove(ws)
```

### Frontend Usage

```javascript
// src/api.js
const ws = new WebSocket('ws://localhost:8000/ws/live');
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  // Update live feed, increment counters, re-fetch stats
  onLiveAction(data);
};
```

---

## 6. Database Schema (Full)

```sql
CREATE TABLE agents (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  name             TEXT UNIQUE NOT NULL,
  token            TEXT,                    -- JWT (stored for reference)
  status           TEXT DEFAULT 'active',   -- active | suspended | killed
  created_at       DATETIME DEFAULT NOW(),
  permissions_json TEXT                     -- JSON blob of permissions
);

CREATE TABLE policies (
  id                      INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id                INTEGER REFERENCES agents(id),
  action_type             TEXT,
  max_amount              REAL,
  approved_recipients     TEXT,             -- JSON array
  allowed_file_paths      TEXT,             -- JSON array
  requires_approval_above REAL
);

CREATE TABLE actions (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id    INTEGER REFERENCES agents(id),
  action_type TEXT,
  params_json TEXT,                         -- JSON blob of params
  decision    TEXT,                         -- ALLOW | BLOCK | REVIEW
  risk_score  INTEGER,
  reason      TEXT,
  created_at  DATETIME DEFAULT NOW(),
  executed    BOOLEAN DEFAULT FALSE
);

CREATE TABLE approvals (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  action_id   INTEGER REFERENCES actions(id),
  status      TEXT DEFAULT 'pending',       -- pending | approved | rejected
  created_at  DATETIME DEFAULT NOW(),
  resolved_at DATETIME
);

CREATE TABLE audit_logs (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id     INTEGER REFERENCES agents(id),
  event_type   TEXT,                        -- ACTION_AUTHORIZED, AGENT_KILLED, etc.
  details_json TEXT,                        -- JSON blob
  created_at   DATETIME DEFAULT NOW()
);

CREATE TABLE rate_tracking (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  agent_id     INTEGER REFERENCES agents(id),
  action_type  TEXT,
  window_start DATETIME,
  count        INTEGER DEFAULT 1
);
```

---

## 7. OWASP LLM Top 10 Alignment

| OWASP ID | Risk Name | AgentShield Component | Implementation |
|----------|----------|----------------------|----------------|
| **LLM01** | Prompt Injection | Injection Scanner (Stage 5) | Keyword pattern matching in context + params |
| **LLM02** | Insecure Output Handling | Policy Engine (Stage 3) | Validates all outputs against policy before execution |
| **LLM06** | Excessive Agency | Policy Enforcement | Per-agent action type allowlists, amount caps, recipient whitelists |
| **LLM07** | System Prompt Leakage | JWT Payload Design | Permissions embedded in token, not exposed in prompts |
| **LLM08** | Excessive Permissions | Principle of Least Privilege | Each agent has minimal required permissions only |
| **LLM09** | Overreliance | Human Approval Center | REVIEW tier routes decisions to humans |
| **LLM10** | Model Theft / DoS | Anomaly Detector (Stage 4) | Rate limiting with auto-suspension |

---

## 8. Deployment Architecture (Production Extension)

```
                        ┌──────────────┐
                        │  Load Balancer│
                        └──────┬───────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
      ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
      │ AgentShield  │ │ AgentShield  │ │ AgentShield  │
      │  Instance 1  │ │  Instance 2  │ │  Instance N  │
      └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
             └────────────────┼────────────────┘
                              │
                     ┌────────▼────────┐
                     │   PostgreSQL    │
                     │  (shared state) │
                     └─────────────────┘
                              │
                     ┌────────▼────────┐
                     │  Redis Pub/Sub  │
                     │ (WS broadcast)  │
                     └─────────────────┘
```

> **Note:** The hackathon implementation uses SQLite (single-file) for zero-dependency setup. A production deployment would use PostgreSQL for the database and Redis for distributed WebSocket pub/sub.
