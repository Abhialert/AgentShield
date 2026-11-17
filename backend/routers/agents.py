import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
import auth
from database import get_db

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.post("", response_model=schemas.AgentCreatedOut)
def create_agent(payload: schemas.AgentCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Agent).filter(models.Agent.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Agent name already exists")

    agent = models.Agent(
        name=payload.name,
        permissions_json=json.dumps(payload.permissions),
        status="active",
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    token = auth.create_agent_token(agent.id, payload.permissions)
    # Store raw token (internal use by gateway/attack-lab) and its hash
    agent.token = token
    agent.token_hash = auth.hash_token(token)
    db.commit()
    db.refresh(agent)

    log = models.AuditLog(
        agent_id=agent.id,
        event_type="AGENT_CREATED",
        details_json=json.dumps({"name": agent.name, "permissions": payload.permissions}),
    )
    db.add(log)
    db.commit()

    # Return token ONCE in creation response — caller must save it
    return schemas.AgentCreatedOut(
        id=agent.id,
        name=agent.name,
        status=agent.status,
        created_at=agent.created_at,
        permissions_json=agent.permissions_json,
        token=token,
    )


@router.get("", response_model=List[schemas.AgentOut])
def list_agents(db: Session = Depends(get_db)):
    """List agents — tokens are NOT returned."""
    return db.query(models.Agent).order_by(models.Agent.created_at.desc()).all()


@router.post("/{agent_id}/kill")
def kill_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent.status = "suspended"
    db.commit()

    pending_approvals = (
        db.query(models.Approval)
        .join(models.Action, models.Approval.action_id == models.Action.id)
        .filter(
            models.Action.agent_id == agent_id,
            models.Approval.status == "pending",
        )
        .all()
    )
    for approval in pending_approvals:
        approval.status = "rejected"
    db.commit()

    log = models.AuditLog(
        agent_id=agent_id,
        event_type="AGENT_KILLED",
        details_json=json.dumps({"invalidated_approvals": len(pending_approvals)}),
    )
    db.add(log)
    db.commit()

    return {"message": f"Agent {agent.name} suspended", "invalidated_approvals": len(pending_approvals)}


@router.post("/{agent_id}/reactivate")
def reactivate_agent(agent_id: str, db: Session = Depends(get_db)):
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.status == "killed":
        raise HTTPException(status_code=400, detail="Cannot reactivate a permanently killed agent")

    agent.status = "active"
    db.commit()

    log = models.AuditLog(
        agent_id=agent_id,
        event_type="AGENT_REACTIVATED",
        details_json=json.dumps({"name": agent.name}),
    )
    db.add(log)
    db.commit()

    return {"message": f"Agent {agent.name} reactivated"}
