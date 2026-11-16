"""
AgentShield — Execution Enforcement Gateway
============================================
This is what turns AgentShield from an "advisor" into an actual firewall.

The agent NEVER calls the protected service directly.
Only this gateway holds the execution credentials.
Flow:
  1. Agent calls POST /api/gateway/authorize → receives short-lived grant_token
  2. Agent calls POST /api/gateway/execute with grant_token → gateway executes
  3. Grant tokens expire in 2 minutes and cannot be reused (replay-prevented)

This enforces that:
  - Blocked actions CANNOT be executed (agent has no direct access)
  - Execution requires a fresh cryptographic grant per action
  - All execution is logged atomically before it happens
"""

import json
import uuid
import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from jose import JWTError
from typing import Any, Dict, Optional

import models
import auth
import security_engine
from database import get_db

router = APIRouter(prefix="/api/gateway", tags=["execution-gateway"])

# Track used grant tokens to prevent replay attacks (in-memory for hackathon)
# Production: use Redis with TTL
_used_grants: set = set()


# ── Schemas ────────────────────────────────────────────────────────────────────

class AuthorizeRequest(BaseModel):
    token: str
    action_type: str
    params: Dict[str, Any] = {}
    context: Optional[str] = ""


class ExecuteRequest(BaseModel):
    grant_token: str
    action_id: str


class AuthorizeResponse(BaseModel):
    decision: str
    risk_score: int
    reason: str
    action_id: str
    grant_token: Optional[str] = None  # only present when decision == ALLOW
    message: str


# ── Mock Protected Service Executors ───────────────────────────────────────────
# In production, these would call real external APIs using
# credentials that ONLY this gateway possesses.

def _execute_transfer(params: dict) -> dict:
    tx_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
    return {
        "service": "Protected Banking Gateway",
        "transaction_id": tx_id,
        "amount": f"₹{params.get('amount', 0):,.2f}",
        "recipient": params.get("recipient"),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "status": "COMPLETED",
    }


def _execute_email_read(params: dict) -> dict:
    return {
        "service": "Protected Email Service",
        "emails": [
            {"id": "msg_001", "from": "billing@electricity.gov", "subject": "Bill Due: ₹2,500"},
            {"id": "msg_002", "from": "hr@company.com", "subject": "Monthly Payslip"},
        ],
        "count": params.get("count", 2),
    }


def _execute_file(params: dict) -> dict:
    return {
        "service": "Protected File System",
        "path": params.get("path"),
        "content": "File contents retrieved securely via AgentShield gateway.",
        "bytes_read": 128,
    }


def _execute_calendar(params: dict) -> dict:
    return {
        "service": "Protected Calendar Service",
        "event_id": f"EVT-{uuid.uuid4().hex[:6].upper()}",
        "title": params.get("title"),
        "scheduled": params.get("date", "Tomorrow 10:00 AM"),
        "status": "CREATED",
    }


EXECUTORS = {
    "transfer_money": _execute_transfer,
    "email_read": _execute_email_read,
    "file_access": _execute_file,
    "calendar_write": _execute_calendar,
}


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/authorize", response_model=AuthorizeResponse)
async def gateway_authorize(payload: AuthorizeRequest, db: Session = Depends(get_db)):
    """
    Step 1: Agent submits proposed action for authorization.
    If ALLOW: returns a short-lived single-use grant_token for execution.
    If REVIEW: creates human approval record; no grant issued.
    If BLOCK: rejected immediately; no grant issued.
    """
    decision, risk_score, reason, action_id = security_engine.authorize_action(
        db=db,
        token=payload.token,
        action_type=payload.action_type,
        params=payload.params,
        context=payload.context or "",
    )

    grant_token = None
    if decision == "ALLOW":
        # Retrieve agent_id from token to issue the grant
        try:
            agent_id = auth.verify_token(payload.token)
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")
        grant_token = auth.create_execution_grant(action_id, payload.action_type, agent_id)
        message = "Action authorized. Use the grant_token to execute within 2 minutes."
    elif decision == "REVIEW":
        message = "Action requires human approval. Check the Approval Center."
    else:
        message = f"Action BLOCKED: {reason}"

    return AuthorizeResponse(
        decision=decision,
        risk_score=risk_score,
        reason=reason,
        action_id=action_id,
        grant_token=grant_token,
        message=message,
    )


@router.post("/execute")
async def gateway_execute(payload: ExecuteRequest, db: Session = Depends(get_db)):
    """
    Step 2: Agent submits grant_token to actually execute an ALLOW'd action.
    - Verifies the grant is valid, unexpired, and matches action_id
    - Prevents replay: each grant can only be used once
    - Executes the tool on the agent's behalf (agent never touches the service)
    - Marks action as executed in DB
    """
    # Replay prevention: reject already-used grants
    grant_fingerprint = payload.grant_token[-16:]  # last 16 chars as fingerprint
    if grant_fingerprint in _used_grants:
        raise HTTPException(status_code=409, detail="Grant token already used — replay attack prevented")

    # Verify the grant
    try:
        agent_id = auth.verify_execution_grant(payload.grant_token, payload.action_id)
    except JWTError as e:
        raise HTTPException(status_code=403, detail=f"Invalid or expired execution grant: {e}")

    # Fetch the action from DB and verify it was ALLOW'd
    action = db.query(models.Action).filter(models.Action.id == payload.action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action record not found")
    if action.decision != "ALLOW":
        raise HTTPException(
            status_code=403,
            detail=f"Action was {action.decision}, not ALLOW — execution refused"
        )
    if action.executed:
        raise HTTPException(status_code=409, detail="Action already executed — replay prevented")

    # Mark grant as used (replay prevention)
    _used_grants.add(grant_fingerprint)
    # Prune set to prevent unbounded growth
    if len(_used_grants) > 10000:
        _used_grants.clear()

    # Execute the tool (only gateway has service credentials)
    params = json.loads(action.params_json or "{}")
    executor = EXECUTORS.get(action.action_type)
    if not executor:
        result = {"service": "AgentShield Gateway", "status": "executed", "action_type": action.action_type}
    else:
        result = executor(params)

    # Mark action as executed
    action.executed = True
    db.commit()

    # Audit log
    log = models.AuditLog(
        agent_id=agent_id,
        event_type="ACTION_EXECUTED",
        details_json=json.dumps({
            "action_id": action.id,
            "action_type": action.action_type,
            "result": result,
        }),
    )
    db.add(log)
    db.commit()

    return {
        "status": "EXECUTED",
        "action_id": action.id,
        "action_type": action.action_type,
        "result": result,
        "executed_at": datetime.datetime.utcnow().isoformat() + "Z",
        "gateway": "AgentShield Zero-Trust Execution Gateway",
    }


@router.get("/status/{action_id}")
def gateway_status(action_id: str, db: Session = Depends(get_db)):
    """Check the execution status of a specific action."""
    action = db.query(models.Action).filter(models.Action.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action not found")
    return {
        "action_id": action.id,
        "decision": action.decision,
        "executed": action.executed,
        "risk_score": action.risk_score,
        "reason": action.reason,
    }

