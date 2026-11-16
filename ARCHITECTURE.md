# 🏗️ AgentShield — Technical Architecture

> Comprehensive architectural breakdown of AgentShield's zero-trust execution enforcement gateway, policy engine, and adversarial testing harness.

---

## 1. Zero-Trust Security Gateway Pipeline

Every proposed action follows a strict **two-step cryptographic interception model**:

```
AI Agent (Proposed Action)
     │
     │  1. POST /api/gateway/authorize
     │  Body: { token, action_type, params, context }
     ▼
┌────────────────────────────────────────────────────────────────┐
│                     STAGE 1: JWT Verification                  │
│  auth.py → verify_token(token)                                 │
│                                                                │
│  ✓ Decode JWT with HS256 using AGENTSHIELD_SECRET              │
│  ✓ Check timestamp & expiry claim (24h default lifetime)       │
│  ✓ Replay-safe JTI identifier tracking                         │
│  ✗ Invalid / expired → immediate BLOCK (fail-closed)           │
└──────────────────────────────┬─────────────────────────────────┘
                               │ agent_id confirmed
                               ▼
┌────────────────────────────────────────────────────────────────┐
│                   STAGE 2: Agent Status Check                  │
│  DB lookup: agents WHERE id = agent_id                         │
│                                                                │
│  ✓ status == "active" → proceed                                │
│  ✗ status == "suspended" → BLOCK ("Agent suspended")           │
│  ✗ status == "killed"    → BLOCK ("Agent killed")              │
└──────────────────────────────┬─────────────────────────────────┘
                               │ agent is active
                               ▼
┌────────────────────────────────────────────────────────────────┐
│            STAGE 3: Deterministic Policy Enforcement           │
│  security_engine.py → evaluate_policy()                        │
│                                                                │
│  ✓ Check allowed action types against agent manifest           │
│  ✓ Financial transfers:                                        │
│      • recipient in approved_recipients (UNAPPROVED = HARD BLOCK)
│      • amount ≤ max_amount (EXCEEDED = HARD BLOCK)             │
│  ✓ File access:                                                │
│      • Canonical path containment using pathlib.Path.resolve() │
│      • Traversal sequences (../../) = HARD BLOCK               │
│  ✗ Any deterministic policy violation → instant HARD BLOCK    │
└──────────────────────────────┬─────────────────────────────────┘
                               │ deterministic checks pass
                               ▼
┌────────────────────────────────────────────────────────────────┐
│               STAGE 4: Sliding-Window Anomaly Check            │
│  anomaly_detector.py → check_rate(agent_id, action_type)       │
│                                                                │
│  • Rolling 60-second window: count actions in rate_tracking    │
│  • Rate > 10 req/min → anomaly flag set (+30 risk points)      │
│  • Rate > 20 req/min → critical threshold: auto-suspend agent  │
└──────────────────────────────┬─────────────────────────────────┘
                               │ anomaly metrics collected
                               ▼
┌────────────────────────────────────────────────────────────────┐
│         STAGE 5: Multi-Layer Prompt Injection Scanner          │
│  security_engine.py → _detect_injection(context)               │
│                                                                │
│  1. Strip zero-width & invisible Unicode control characters    │
│  2. Apply Unicode NFKC normalization (catches homoglyphs)      │
│  3. Decode Base64-encoded strings within context payload       │
│  4. Match against pre-compiled regex attack signatures         │
│  • Pattern matched → injection flag set (+50 risk points)      │
└──────────────────────────────┬─────────────────────────────────┘
                               │ scan complete
                               ▼
┌────────────────────────────────────────────────────────────────┐
│                  STAGE 6: Dynamic Risk Scoring                 │
│                                                                │
│  Risk Score (0–100):                                           │
│    + 20  if amount > 80% of policy limit                       │
│    + 30  if anomaly detected (>10 req/min)                     │
│    + 50  if injection pattern detected                         │
│                                                                │
│  Decision:                                                     │
│    score <  30  →  ALLOW                                       │
│    30 ≤ score < 70  →  REVIEW (creates pending approval)       │
│    score ≥  70  →  BLOCK (or hard-block trigger)               │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────┐
│             STAGE 7: Execution Grant Issuance (ALLOW)          │
│                                                                │
│  • Mint short-lived, single-use Execution Grant (JWT):         │
│      - sub: agent_id                                           │
│      - action_id: UUID                                         │
│      - exp: 2 minutes                                          │
│      - type: "execution_grant"                                 │
│  • Broadcast action to WebSocket clients: /ws/live             │
│  • Return: { decision, risk_score, grant_token, action_id }    │
└──────────────────────────────┬─────────────────────────────────┘
                               │
                               │ Agent presents grant
                               ▼
┌────────────────────────────────────────────────────────────────┐
│         STAGE 8: Cryptographic Execution Interception          │
│  POST /api/gateway/execute                                     │
│  Body: { grant_token, action_id }                              │
│                                                                │
│  ✓ Verify grant token signature & 2-minute expiry              │
│  ✓ Verify grant action_id matches request                      │
│  ✓ Verify grant has not been redeemed (replay prevention)      │
│  ✓ Mark action executed = True in atomic transaction           │
│  ✗ Expired or already used grant → 409 Conflict                │
│  ✓ Forward request to protected internal service               │
└────────────────────────────────────────────────────────────────┘
```

---

## 2. Execution Gateway vs. Advisory Firewalls

Traditional agent guardrails operate purely as advisory text classifiers: an agent calls an API, the guardrail suggests whether the text is safe, and the agent is expected to voluntarily comply.

AgentShield implements **True Execution Interception**:

```
Advisory Guardrail (Vulnerable):
AI Agent ────► Guardrail (Returns: "Please don't do this") ────► AI Agent (Ignores & calls Bank API directly)

AgentShield Execution Gateway (Enforced):
AI Agent ────► AgentShield (/api/gateway/authorize)
                     │
            [ALLOW + Grant Token]
                     │
AI Agent ────► AgentShield (/api/gateway/execute) ────► Protected Bank API
                     ▲
          (Zero credentials held by agent)
```

The AI agent holds **zero direct credentials** to underlying services. Only the AgentShield gateway holds execution credentials. Without a valid, unredeemed execution grant token minted by AgentShield, calling downstream services is cryptographically impossible.

---

## 3. Adversarial Attack Lab Architecture

AgentShield includes an automated red-team test harness (`/api/attack-lab/`) to benchmark security capabilities across 8 attack categories:

```
┌────────────────────────────────────────────────────────────────────────┐
│                     Adversarial Attack Suite                           │
├──────────┬───────────────────────────────┬─────────────────────────────┤
│ ID       │ Attack Name                   │ Defense Mechanism           │
├──────────┼───────────────────────────────┼─────────────────────────────┤
│ ATK-001  │ Direct Amount Limit Violation │ Policy max_amount boundary  │
│ ATK-002  │ Unknown Recipient (₹100)      │ Zero-trust hard block       │
│ ATK-003  │ Classic Prompt Injection      │ Context threat scanner      │
│ ATK-004  │ Base64-Encoded Injection      │ Automatic Base64 decode     │
│ ATK-005  │ Path Traversal (../../)       │ pathlib canonical sandbox   │
│ ATK-006  │ Path Prefix Confusion         │ Directory boundary match    │
│ ATK-007  │ Cross-Agent Permission Abuse  │ Manifest action scope check │
│ ATK-008  │ Unicode Homoglyph Injection   │ NFKC Unicode normalization  │
└──────────┴───────────────────────────────┴─────────────────────────────┘
```

---

## 4. Database Schema

AgentShield stores all state in SQLite via SQLAlchemy 2.0 with foreign keys and cascading relationships:

```
┌──────────────┐         1:N         ┌───────────────┐
│    agents    │────────────────────►│   policies    │
└──────┬───────┘                     └───────────────┘
       │
       │ 1:N
       ▼
┌──────────────┐         1:1         ┌───────────────┐
│   actions    │────────────────────►│   approvals   │
└──────┬───────┘                     └───────────────┘
       │
       │ 1:N
       ▼
┌──────────────┐
│  audit_logs  │
└──────────────┘
```

- **`agents`**: Stores agent identity, status (`active`, `suspended`, `killed`), permission manifests, and active JWT.
- **`policies`**: Per-agent constraints (`max_amount`, `approved_recipients`, `allowed_file_paths`, `requires_approval_above`).
- **`actions`**: Log of every proposed action with decision (`ALLOW`, `REVIEW`, `BLOCK`), risk score, reason, execution status, and timestamp.
- **`approvals`**: Human-in-the-loop pending tickets generated for `REVIEW` decisions, updated upon human review.
- **`audit_logs`**: Immutable forensic event trail (`AGENT_SEEDED`, `ACTION_BLOCKED`, `AGENT_KILLED`, `APPROVAL_GRANTED`).
- **`rate_tracking`**: Timestamped action occurrences used by the 60-second sliding-window anomaly detector.
