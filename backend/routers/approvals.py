"""
AgentShield — Approvals Router
Human-in-the-loop approval workflow.
Approving an action now triggers the real executor via the gateway.
"""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from database import get_db
from routers.gateway import EXECUTORS

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.get("", response_model=List[schemas.ApprovalOut])
def list_all_approvals(db: Session = Depends(get_db)):
    return (
        db.query(models.Approval)
        .order_by(models.Approval.created_at.desc())
        .limit(50)
        .all()
    )


@router.get("/completed", response_model=List[schemas.ApprovalOut])
def list_completed_approvals(db: Session = Depends(get_db)):
    return (
        db.query(models.Approval)
        .filter(models.Approval.status.in_(["approved", "rejected"]))
        .order_by(models.Approval.resolved_at.desc())
        .limit(50)
        .all()
    )


@router.get("/pending", response_model=List[schemas.ApprovalOut])
def list_pending_approvals(db: Session = Depends(get_db)):
    return (
        db.query(models.Approval)
        .filter(models.Approval.status == "pending")
        .order_by(models.Approval.created_at.desc())
        .all()
    )


@router.post("/{action_id}/approve", response_model=schemas.ApprovalOut)
def approve_action(action_id: str, db: Session = Depends(get_db)):
    approval = (
        db.query(models.Approval)
        .filter(models.Approval.action_id == action_id)
        .first()
    )
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail=f"Approval is already {approval.status}")

    action = db.query(models.Action).filter(models.Action.id == action_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Action record not found")

    # Invoke the real executor — only mark executed after success
    executor = EXECUTORS.get(action.action_type)
    execution_result = None
    if executor:
        params = json.loads(action.params_json or "{}")
        execution_result = executor(params)
        action.executed = True
    else:
        # No registered executor: approve the record but flag as not executed
        execution_result = {
            "warning": f"No executor registered for '{action.action_type}'. Approval recorded but action not executed."
        }

    approval.status = "approved"
    approval.resolved_at = datetime.utcnow()
    approval.execution_result = json.dumps(execution_result)
    db.commit()

    log = models.AuditLog(
        agent_id=action.agent_id,
        event_type="APPROVAL_APPROVED",
        details_json=json.dumps({
            "action_id": action_id,
            "action_type": action.action_type,
            "executed": action.executed,
            "result": execution_result,
        }),
    )
    db.add(log)
    db.commit()

    db.refresh(approval)
    return approval


@router.post("/{action_id}/reject", response_model=schemas.ApprovalOut)
def reject_action(action_id: str, db: Session = Depends(get_db)):
    approval = (
        db.query(models.Approval)
        .filter(models.Approval.action_id == action_id)
        .first()
    )
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found")
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail=f"Approval is already {approval.status}")

    approval.status = "rejected"
    approval.resolved_at = datetime.utcnow()
    db.commit()

    action = db.query(models.Action).filter(models.Action.id == action_id).first()
    if action:
        log = models.AuditLog(
            agent_id=action.agent_id,
            event_type="APPROVAL_REJECTED",
            details_json=json.dumps({"action_id": action_id, "action_type": action.action_type}),
        )
        db.add(log)
        db.commit()

    db.refresh(approval)
    return approval
