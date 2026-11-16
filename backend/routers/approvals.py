import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from database import get_db

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

    approval.status = "approved"
    approval.resolved_at = datetime.utcnow()
    db.commit()

    # Mark the action as executed
    action = db.query(models.Action).filter(models.Action.id == action_id).first()
    if action:
        action.executed = True
        db.commit()
        log = models.AuditLog(
            agent_id=action.agent_id,
            event_type="APPROVAL_APPROVED",
            details_json=json.dumps({"action_id": action_id, "action_type": action.action_type}),
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
