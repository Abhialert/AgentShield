# AgentShield Backend

A FastAPI-powered security firewall for AI agents. The backend enforces policies, detects anomalies, and requires human approval for risky actions before any AI agent can execute them.

---

## Quick Start

```bash
cd backend

# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`.  
Interactive docs: `http://localhost:8000/docs`

---

## Project Structure

```
backend/
├── main.py              # FastAPI app, startup seeding, WebSocket
├── database.py          # SQLite + SQLAlchemy engine/session
├── models.py            # ORM models
├── schemas.py           # Pydantic request/response schemas
├── auth.py              # JWT creation and verification
├── security_engine.py   # Core policy enforcement + risk scoring
├── anomaly_detector.py  # Rate-based anomaly detection
├── routers/
│   ├── agents.py        # Agent CRUD + kill/reactivate
│   ├── actions.py       # POST /api/actions/authorize (main endpoint)
│   ├── approvals.py     # Human approval workflow
│   ├── audit.py         # Audit log + dashboard stats
│   └── demo.py          # Demo scenarios + reset
├── requirements.txt
└── agentshield.db       # SQLite DB (auto-created on first run)
```

---

## Seed Agents (created automatically on startup)

| Agent | Allowed Actions | Policy |
|---|---|---|
| `agent_payment` | `transfer_money` | max $5,000 · approved: electricity_board, water_dept, gas_provider |
| `agent_email` | `email_read`, `email_delete`, `file_access` | files limited to `documents/` |
| `agent_calendar` | `calendar_read`, `calendar_write` | unrestricted |

---

## Key Endpoints

### Agent Management
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/agents` | Register new agent → returns JWT |
| `GET` | `/api/agents` | List all agents |
| `POST` | `/api/agents/{id}/kill` | Suspend agent + invalidate pending approvals |
| `POST` | `/api/agents/{id}/reactivate` | Reactivate suspended agent |

### Action Authorization ⭐
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/actions/authorize` | Main security gate |
| `GET` | `/api/actions` | Last 50 actions |

**Request body:**
```json
{
  "token": "<agent JWT>",
  "action_type": "transfer_money",
  "params": { "amount": 2500, "recipient": "electricity_board" },
  "context": "optional free-text context checked for prompt injection"
}
```

**Response:**
```json
{
  "decision": "ALLOW",
  "risk_score": 0,
  "reason": "All checks passed",
  "action_id": "uuid"
}
```

### Approvals
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/approvals/pending` | List pending human approvals |
| `POST` | `/api/approvals/{action_id}/approve` | Approve |
| `POST` | `/api/approvals/{action_id}/reject` | Reject |

### Audit & Dashboard
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/audit` | Last 100 audit log entries |
| `GET` | `/api/dashboard/stats` | Counts + threat level |

### Demo
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/demo/run-scenario` | Run `legitimate`, `prompt_injection`, or `anomaly_flood` |
| `GET` | `/api/demo/reset` | Wipe all data and re-seed |

### WebSocket
```
ws://localhost:8000/ws/live
```
Receives real-time JSON events whenever an action is authorized.

---

## Security Engine — Decision Logic

```
risk_score = 0
1. JWT invalid/expired          → BLOCK (100)
2. Agent suspended/killed       → BLOCK (100)
3. Action type not permitted    → BLOCK (100)
4. Prompt injection in context  → +10
5. Anomaly detected (>10/min)   → +30
6. Unknown recipient            → +40
7. Amount > 80% of limit        → +20
8. email_delete                 → minimum REVIEW

ALLOW  : risk < 30
REVIEW : 30 ≤ risk < 70
BLOCK  : risk ≥ 70  OR  hard rule violation
```

---

## Anomaly Detection

Tracks requests per agent per 60-second rolling window:
- **> 10 req/min** → Suspicious (+30 risk)
- **> 20 req/min** → Critical → agent **auto-suspended**

---

## Environment / Configuration

| Setting | Value |
|---|---|
| Database | `./agentshield.db` (SQLite) |
| Port | `8000` |
| JWT Secret | `agentshield-secret-2024` *(hardcoded for hackathon)* |
| CORS | All origins allowed |
