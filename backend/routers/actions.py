import json
import asyncio
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

import models
import schemas
import security_engine
from database import get_db

router = APIRouter(prefix="/api/actions", tags=["actions"])

# WebSocket manager reference — injected at startup
_ws_manager = None


def set_ws_manager(manager):
    global _ws_manager
    _ws_manager = manager


@router.post("/authorize", response_model=schemas.AuthorizeResponse)
async def authorize_action(payload: schemas.AuthorizeRequest, db: Session = Depends(get_db)):
    decision, risk_score, reason, action_id = security_engine.authorize_action(
        db=db,
        token=payload.token,
        action_type=payload.action_type,
        params=payload.params,
        context=payload.context or "",
    )

    # Broadcast to WebSocket clients
    if _ws_manager:
        event = {
            "event": "action",
            "action_id": action_id,
            "decision": decision,
            "risk_score": risk_score,
            "action_type": payload.action_type,
            "reason": reason,
        }
        await _ws_manager.broadcast(json.dumps(event))

    return schemas.AuthorizeResponse(
        decision=decision,
        risk_score=risk_score,
        reason=reason,
        action_id=action_id,
    )


@router.get("", response_model=List[schemas.ActionOut])
def list_actions(db: Session = Depends(get_db)):
    return (
        db.query(models.Action)
        .order_by(models.Action.created_at.desc())
        .limit(50)
        .all()
    )
