from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
from database import get_db

router = APIRouter(prefix="/api", tags=["audit"])


@router.get("/audit", response_model=List[schemas.AuditLogOut])
def get_audit_log(db: Session = Depends(get_db)):
    return (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.created_at.desc())
        .limit(100)
        .all()
    )


@router.get("/dashboard/stats")
def dashboard_stats(db: Session = Depends(get_db)):
    total = db.query(models.Action).count()
    blocked = db.query(models.Action).filter(models.Action.decision == "BLOCK").count()
    allowed = db.query(models.Action).filter(models.Action.decision == "ALLOW").count()
    review = db.query(models.Action).filter(models.Action.decision == "REVIEW").count()

    # Threat level calculation
    if total == 0:
        threat_level = "LOW"
    else:
        block_ratio = blocked / total
        if block_ratio >= 0.5:
            threat_level = "CRITICAL"
        elif block_ratio >= 0.3:
            threat_level = "HIGH"
        elif block_ratio >= 0.1:
            threat_level = "MEDIUM"
        else:
            threat_level = "LOW"

    agents = db.query(models.Agent).order_by(models.Agent.created_at).all()
    agents_data = [
        {"id": a.id, "name": a.name, "status": a.status}
        for a in agents
    ]

    return {
        "total_actions": total,
        "blocked": blocked,
        "allowed": allowed,
        "review": review,
        "active_agents": sum(1 for a in agents if a.status == "active"),
        "threat_level": threat_level,
        "agents": agents_data,
    }
