"""
AgentShield — /api/chat endpoint
=================================
Routes natural-language user messages through the deterministic AgentRunner
(Layer 1) which extracts tool calls and enforces them via the security gateway.

On Nov 21 live sprint: replace AgentRunner._parse_intent() with Gemini function calling.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db
from ai_agent import AgentRunner
from typing import Optional

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    agent_name: str = "agent_payment"


class ChatResponse(BaseModel):
    response: str
    decision: Optional[str] = None
    risk_score: Optional[int] = None
    reason: Optional[str] = None
    action_id: Optional[str] = None
    tool_proposed: Optional[str] = None


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    runner = AgentRunner(agent_name=payload.agent_name, db_session=db)
    result = await runner.run(payload.message)
    return ChatResponse(
        response=result["response"],
        decision=result.get("decision"),
        risk_score=result.get("risk_score"),
        reason=result.get("reason"),
        action_id=result.get("action_id"),
        tool_proposed=result.get("tool_proposed"),
    )


@router.get("/stream")
async def chat_stream(
    message: str,
    agent_name: str = "agent_payment",
    db: Session = Depends(get_db)
):
    """
    Streaming SSE endpoint.
    Layer 1: yields full result in one SSE event.
    Layer 2 (Nov 21): stream tokens from Gemini with live tool-call badges.
    """
    runner = AgentRunner(agent_name=agent_name, db_session=db)

    async def generate():
        async for chunk in runner.stream_run(message):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
