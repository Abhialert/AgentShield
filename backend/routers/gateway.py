"""
AgentShield — Execution Enforcement Gateway
============================================
Two-stage cryptographic execution model:
  1. POST /api/gateway/authorize → security engine evaluates; ALLOW issues grant_token + persists ExecutionGrant row
  2. POST /api/gateway/execute   → atomic consume of grant (consumed_at set in single UPDATE WHERE consumed_at IS NULL)
     → only then does protected executor run

Replay prevention is database-backed and multi-worker safe.
"""

import json
import uuid
import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import update
from jose import JWTError
from typing import Any, Dict, Optional

import models
import auth
import security_engine
from database import get_db

router = APIRouter(prefix="/api/gateway", tags=["execution-gateway"])


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
    grant_token: Optional[str] = None
    message: str


# ── Executor Allowlist (explicit — unknown actions are REJECTED) ───────────────

def _execute_transfer(params: dict) -> dict:
    tx_id = f"TXN-{uuid.uuid4().hex[:8].upper()}"
    return {
        "service": "Simulated Banking Gateway",
        "transaction_id": tx_id,
        "amount": f"₹{params.get('amount', 0):,.2f}",
        "recipient": params.get("recipient"),
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "status": "COMPLETED",
    }


def _execute_email_read(params: dict) -> dict:
    return {
        "service": "Simulated Email Service",
        "emails": [
            {"id": "msg_001", "from": "billing@electricity.gov", "subject": "Bill Due: ₹2,500"},
            {"id": "msg_002", "from": "hr@company.com", "subject": "Monthly Payslip"},
        ],
        "count": params.get("count", 2),
    }


def _execute_file(params: dict) -> dict:
    return {
        "service": "Simulated File System",
        "path": params.get("path"),
        "content": "File contents retrieved securely via AgentShield gateway.",
        "bytes_read": 128,
    }


def _execute_calendar(params: dict) -> dict:
    return {
        "service": "Simulated Calendar Service",
        "event_id": f"EVT-{uuid.uuid4().hex[:6].upper()}",
        "title": params.get("title"),
        "scheduled": params.get("date", "Tomorrow 10:00 AM"),
        "status": "CREATED",
    }


# Explicit allowlist: any action_type not in this dict is REJECTED
EXECUTORS: Dict[str, Any] = {
    "transfer_money": _execute_transfer,
    "email_read": _execute_email_read,
    "file_access": _execute_file,
    "calendar_write": _execute_calendar,
}


# ── Helper: atomic grant consumption ──────────────────────────────────────────

def _consume_grant_atomic(db: Session, jti: str) -> bool:
    """
    Atomically consume an execution grant by setting consumed_at.
    Returns True if this call consumed it (first use), False if already used.
    Uses UPDATE WHERE consumed_at IS NULL — safe across multiple workers.
    """
    now = datetime.datetime.utcnow()
    result = db.execute(
        update(models.ExecutionGrant)
        .where(
            models.ExecutionGrant.jti == jti,
            models.ExecutionGrant.consumed_at.is_(None),
            models.ExecutionGrant.expires_at > now,
        )
        .values(consumed_at=now)
    )
    db.commit()
    return result.rowcount == 1


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.post("/authorize", response_model=AuthorizeResponse)
async def gateway_authorize(payload: AuthorizeRequest, db: Session = Depends(get_db)):
    """
    Step 1: Evaluate proposed action. If ALLOW, mint & persist a single-use ExecutionGrant.
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
        try:
            agent_id = auth.verify_token(payload.token)
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Reject unsupported action types even on ALLOW
        if payload.action_type not in EXECUTORS:
            raise HTTPException(
                status_code=400,
                detail=f"Action type '{payload.action_type}' has no registered executor — rejected"
            )

        grant_token, jti = auth.create_execution_grant(action_id, payload.action_type, agent_id)

        # Persist grant to DB (atomic replay prevention)
        grant_row = models.ExecutionGrant(
            action_id=action_id,
            jti=jti,
            expires_at=datetime.datetime.utcnow() + datetime.timedelta(minutes=2),
        )
        db.add(grant_row)
        db.commit()

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
    Step 2: Atomically consume grant and execute the tool.
    - DB-backed replay prevention (multi-worker safe)
    - Executor allowlist enforced
    - Protected service only called after atomic grant consumption
    """
    # Verify JWT signature and extract jti
    try:
        agent_id, jti = auth.verify_execution_grant(payload.grant_token, payload.action_id)
    except JWTError as e:
        raise HTTPException(status_code=403, detail=f"Invalid or expired execution grant: {e}")

    # Atomic grant consumption — prevents replay under concurrent requests
    consumed = _consume_grant_atomic(db, jti)
    if not consumed:
        raise HTTPException(status_code=409, detail="Grant already used or expired — replay attack prevented")

    # Fetch and validate action
    action = db.query(models.Action).filter(models.Action.id == payload.action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action record not found")
    if action.decision != "ALLOW":
        raise HTTPException(status_code=403, detail=f"Action was {action.decision}, not ALLOW — execution refused")
    if action.executed:
        raise HTTPException(status_code=409, detail="Action already executed")

    # Executor allowlist — reject unknown action types
    executor = EXECUTORS.get(action.action_type)
    if not executor:
        raise HTTPException(
            status_code=400,
            detail=f"No registered executor for action type '{action.action_type}'"
        )

    # Execute via gateway (protected service credentials stay here, not with agent)
    params = json.loads(action.params_json or "{}")
    result = executor(params)

    # Mark executed atomically
    action.executed = True
    db.commit()

    # Audit
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


@router.post("/execute-approved")
async def execute_approved_action(payload: dict, db: Session = Depends(get_db)):
    """
    Called internally after a human approves a REVIEW action.
    Triggers the real executor for the approved action.
    """
    action_id = payload.get("action_id")
    action = db.query(models.Action).filter(models.Action.id == action_id).first()
    if not action or action.decision != "REVIEW":
        raise HTTPException(status_code=404, detail="Approved action not found")

    executor = EXECUTORS.get(action.action_type)
    if not executor:
        raise HTTPException(
            status_code=400,
            detail=f"No registered executor for '{action.action_type}'"
        )

    params = json.loads(action.params_json or "{}")
    result = executor(params)

    action.executed = True
    db.commit()

    log = models.AuditLog(
        agent_id=action.agent_id,
        event_type="APPROVAL_EXECUTED",
        details_json=json.dumps({"action_id": action_id, "result": result}),
    )
    db.add(log)
    db.commit()

    return result


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
