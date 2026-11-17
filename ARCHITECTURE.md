# 🏗️ AgentShield — Technical Architecture

> **A Zero-Trust Runtime Enforcement Gateway for Autonomous AI Agents.**
> Model-independent. Cryptographically enforced. Independently verifiable.

---

## 1. The Two-Stage Enforcement Model

AgentShield enforces security through two distinct API calls that the agent must complete in sequence. There is no way for an agent to reach a protected service by bypassing either stage.

### Stage 1 — Authorization (`POST /api/gateway/authorize`)

```
Agent submits: { agent_token, action_type, params, context }

7 Sequential Checks (fail-closed — any failure returns BLOCK immediately):

  CHECK 1: JWT Signature
    auth.verify_token(token)
    → HS256 decode with AGENTSHIELD_SECRET (loaded from .env)
    → token.type must be "agent" (not "execution_grant" or any other type)
    → expired? → BLOCK "Invalid/expired token"

  CHECK 2: Agent Existence & Status
    DB query: agents WHERE id = agent_id
    → not found?           → BLOCK "Agent not found"
    → status == suspended? → BLOCK "Agent is suspended"
    → status == killed?    → BLOCK "Agent is killed"
    (Tokens issued before suspension are immediately invalidated here)

  CHECK 3: Prompt Injection Scan
    _detect_injection(context):
      a. Strip zero-width & invisible Unicode control chars (category Cf, Cs)
      b. NFKC normalization (collapses homoglyphs: ｉｇｎｏｒｅ → ignore)
      c. Base64 auto-decode (chunks ≥8 chars matching [A-Za-z0-9+/=]+)
      d. Regex match against known attack phrases
    → ANY match → hard_block = True, risk_score = 100 (overrides everything)
    Key: even valid params + injection in context = BLOCK.
         Injection means the agent context may be compromised.

  CHECK 4: Permission Manifest
    agent.permissions_json → list of allowed action_types
    → action_type not in list? → BLOCK "Action not permitted"

  CHECK 5: Policy Enforcement (action_type-specific)
    transfer_money:
      → recipient not in approved_recipients? → BLOCK "Unapproved recipient"
      → amount > max_amount?                  → BLOCK "Exceeds policy limit"
    file_access:
      → pathlib.Path(path).resolve() outside allowed_file_paths?
                                              → BLOCK "Path traversal"

  CHECK 6: Anomaly Detection
    60-second sliding window per agent in rate_tracking table
    → rate > 10 req/min  → risk += 30 (anomaly flag)
    → rate > 20 req/min  → agent.status = "suspended" + BLOCK

  CHECK 7: Risk Scoring & Decision
    risk_score accumulates across checks:
      + 20   if amount > 80% of max_amount
      + 30   if anomaly detected
      + 100  if injection detected (hard block)

    ALLOW   → risk < 30       → mint ExecutionGrant (Step 2)
    REVIEW  → 30 ≤ risk < 70  → create Approval record, return action_id
    BLOCK   → risk ≥ 70       → audit log, return 200 with BLOCK decision
```

### Stage 2 — Execution (`POST /api/gateway/execute`)

```
Agent submits: { grant_token, action_id }

  STEP 1: Verify grant JWT signature & expiry
    auth.verify_execution_grant(grant_token, action_id)
    → token.type must be "execution_grant"
    → JWT exp must be in future (2-minute window from issuance)
    → JWT action_id claim must match request body action_id
    → Failure → HTTP 403

  STEP 2: Atomic grant consumption (multi-worker safe)
    DB atomic UPDATE:
      UPDATE execution_grants
        SET consumed_at = NOW()
        WHERE jti = :jti
          AND consumed_at IS NULL
          AND expires_at > NOW()
    → rowcount == 0 → HTTP 409 Conflict "Grant already used or expired"
    → rowcount == 1 → proceed (this thread owns the grant exclusively)

    Why this prevents race conditions:
    SQLite serializes writes. The WHERE consumed_at IS NULL clause means
    only one concurrent UPDATE can succeed. All others find consumed_at
    already set and get rowcount=0. Verified with 20 simultaneous threads:
    exactly 1 success, 19 conflict — every time.

  STEP 3: Action validation
    → Fetch action from DB by action_id
    → action.decision must be "ALLOW" (not BLOCK or REVIEW)
    → action.executed must be False (prevents double-execution)

  STEP 4: Executor allowlist check
    EXECUTORS dict is explicit: { "transfer_money", "email_read",
                                  "file_access", "calendar_write" }
    → action_type not in EXECUTORS → HTTP 400 (not fake success)

  STEP 5: Protected executor call
    result = EXECUTORS[action_type](params)
    → raises exception → action.executed stays False, HTTP 500
    → succeeds → action.executed = True, audit logged

  Agent holds zero direct credentials to any downstream service.
  The executor functions live inside the gateway — the agent never sees them.
```

---

## 2. Replay Prevention: Why It's Concurrency-Safe

A naive implementation uses an in-memory set to track used JTIs:

```python
# VULNERABLE (naive):
if jti in _used_grants:
    raise HTTPException(409)
_used_grants.add(jti)
executor(params)  # Race window here — two threads can both pass the check
```

This fails under concurrency: two threads can both pass the check before either adds to the set.

AgentShield's implementation:

```python
# SAFE (atomic DB UPDATE):
result = db.execute(
    update(ExecutionGrant)
    .where(
        ExecutionGrant.jti == jti,
        ExecutionGrant.consumed_at.is_(None),
        ExecutionGrant.expires_at > now,
    )
    .values(consumed_at=now)
)
db.commit()
consumed = result.rowcount == 1  # True only for one thread
```

The database serializes the write. `WHERE consumed_at IS NULL` is an atomic test-and-set. This is also restart-safe (grants persist in DB, not in RAM) and multi-process safe (each process hits the same DB).

---

## 3. Database Schema

```
agents
  id            UUID PK
  name          TEXT UNIQUE
  status        TEXT  (active | suspended | killed)
  permissions_json TEXT  (["transfer_money", ...])
  token         TEXT  (raw JWT for internal gateway use — NOT returned by API)
  token_hash    TEXT  (SHA-256 of token)
  created_at    DATETIME

policies
  id            UUID PK
  agent_id      UUID FK → agents.id
  action_type   TEXT
  max_amount    FLOAT
  approved_recipients  TEXT (JSON array)
  allowed_file_paths   TEXT (JSON array)
  requires_approval_above FLOAT

actions
  id            UUID PK
  agent_id      UUID FK → agents.id
  action_type   TEXT
  params_json   TEXT
  decision      TEXT  (ALLOW | REVIEW | BLOCK)
  risk_score    INT
  reason        TEXT
  executed      BOOLEAN  (True only after confirmed executor success)
  created_at    DATETIME

execution_grants                         ← Key table (atomic replay prevention)
  id            UUID PK
  action_id     UUID FK → actions.id
  jti           TEXT UNIQUE              ← UniqueConstraint prevents duplicate rows
  expires_at    DATETIME                 ← 2 minutes from issuance
  consumed_at   DATETIME NULL            ← NULL = unused; non-NULL = consumed

approvals
  id            UUID PK
  action_id     UUID FK → actions.id
  status        TEXT  (pending | approved | rejected | failed)
  resolved_at   DATETIME NULL
  execution_result TEXT (JSON — executor output or failure reason)

audit_logs
  id            UUID PK
  agent_id      UUID FK → agents.id
  event_type    TEXT
  details_json  TEXT
  created_at    DATETIME

rate_tracking
  id            UUID PK
  agent_id      UUID FK → agents.id
  action_type   TEXT
  timestamp     DATETIME
```

**Token security design:**
- `agents.token` — raw JWT stored for internal gateway use (AI agent runner needs to call gateway on agent's behalf). Never returned by `GET /api/agents`.
- `agents.token_hash` — SHA-256 of token. Cannot be used as authentication credential (gateway verifies JWT signature, not hash).
- `AgentOut` Pydantic schema: no `token` field, no `token_hash` field.
- `AgentCreatedOut`: includes `token` exactly once, at agent creation time.

---

## 4. Security Engine — Injection Detection Pipeline

```
Input: context string (the natural-language command the agent was given)

Step 1: Invisible character removal
  "".join(c for c in text if unicodedata.category(c) not in ("Cf", "Cs"))
  Removes: zero-width space (U+200B), zero-width joiner (U+200D),
           soft hyphen (U+00AD), and all other format/surrogate chars.

Step 2: NFKC Unicode normalization
  unicodedata.normalize("NFKC", text)
  Collapses: fullwidth chars (ｉｇｎｏｒｅ → ignore),
             superscripts, compatibility equivalents.

Step 3: Base64 decode attempt
  For each whitespace-delimited chunk:
    if len(chunk) >= 8 and chunk matches [A-Za-z0-9+/=]+:
      decoded = base64.b64decode(chunk + "==").decode("utf-8")
      append decoded to scan corpus

Step 4: Regex pattern match
  Patterns include: "ignore previous", "ignore your instructions",
  "you are now", "new instructions", "forget your", "bypass security",
  "ignore agentshield", "jailbreak", "do anything now", "dan mode", etc.
  → Compiled at startup with re.IGNORECASE

Result: ANY match → hard_block = True, risk_score = 100
  Hard block is not additive — it overrides the final decision unconditionally.
  Valid params + injection in context = BLOCK.
  This is the zero-trust stance: injection means the agent may be compromised.
```

---

## 5. AI Agent Architecture (Dual-Layer)

```
User message
     │
     ▼
Layer 1 (Pre-built, active): Deterministic Intent Parser
  _parse_intent(message):
    - Regex extracts tool type, amount, recipient, file path, event title
    - Pattern matched → { tool, params, context }
    - No match → "I can help with: payments, emails, files, calendar"
    50/50 Rule: ZERO LLM API calls in this layer.

Layer 2 (Nov 21 live build): Gemini 1.5 Flash Function Calling
  _call_gemini_llm(message, available_tools):
    - Gemini proposes tool calls via function calling API
    - AgentShield intercepts EVERY proposed call (agent cannot self-authorize)
    - Streaming SSE for real-time output
     │
     ▼
AgentRunner._route_through_agentshield(tool, params, context)
  → security_engine.authorize_action(db, token, action_type, params, context)
  → Returns (decision, risk_score, reason, action_id)
  → Builds natural-language response with enforcement result
```

**Key architectural guarantee:** The LLM never decides whether its own action is safe. The gateway decision is final. If Gemini is manipulated into proposing an unauthorized action, the gateway blocks it and reports `executor_invoked=False`.

---

## 6. Adversarial Attack Lab — Gateway Integration

All 8 attacks route through the real two-stage gateway (not a mock):

```python
# For each attack vector:
1. POST /api/gateway/authorize  → decision, grant_token
2. if decision == "ALLOW":
     POST /api/gateway/execute  → executor_invoked = True
   else:
     executor_invoked = False   # Gateway prevented execution

# attack_lab.py tracks executor_invoked per attack.
# A blocked attack that shows executor_invoked=True is a security failure.
# Target: executor_invoked=0 on all blocked attacks.
```

Verified result: `8/8 intercepted, executor_invoked_on_blocked_attacks=0`

---

## 7. Human Approval Workflow

```
REVIEW decision:
  1. gateway.py creates Approval record (status=pending)
  2. Frontend polls GET /api/approvals/pending every 10s
  3. Human reviews: params, risk_score, reason, agent identity
  4. POST /api/approvals/{action_id}/approve

approve_action():
  executor = EXECUTORS.get(action.action_type)
  try:
      result = executor(params)         ← real executor called
      action.executed = True            ← only set after confirmed success
      approval.status = "approved"
  except Exception as e:
      action.executed = False           ← failure keeps executed=False
      approval.status = "failed"
      approval.execution_result = { error, status: "FAILED" }
      audit log: EXECUTION_FAILED
```

Approval cannot be reused: once `status` is `approved` or `failed`, re-approval raises `HTTP 400 "Approval is already approved/failed"`.

---

## 8. What AgentShield Does NOT Claim

- **Not a production deployment.** Services are simulated (no real bank, no real email).
- **Not a persistent secrets store.** `agents.token` in SQLite is appropriate for a demo; production would use a secrets manager.
- **Not crash-recovery safe.** If the process crashes after the external action succeeds but before `action.executed = True` is written, the state is inconsistent. Production would use a distributed transaction or idempotency key.
- **Not distributed-process tested.** The atomic `UPDATE WHERE consumed_at IS NULL` is safe across SQLite-shared-file processes (SQLite WAL mode), but not across separate database replicas.

These are known limitations documented here so they are not discovered as surprises.
