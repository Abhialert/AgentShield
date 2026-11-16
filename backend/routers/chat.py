"""
AgentShield — /api/chat endpoint
=================================
⚡ LIVE BUILD MODULE (Nov 21, 12:00–05:45 PM)

Connects the LLM agent to AgentShield's security gateway via a streaming
Server-Sent Events (SSE) endpoint. The frontend AgentChat page will call this.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import get_db

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    agent_name: str = "agent_payment"   # which agent runs this request


class ChatResponse(BaseModel):
    response: str
    decision: str | None = None
    risk_score: int | None = None
    action_id: str | None = None


@router.post("", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    """
    LIVE BUILD: wire in the AgentRunner here.

    Current state: returns a placeholder response so the endpoint is reachable.
    On Nov 21, replace the body with:

        from ai_agent import AgentRunner
        runner = AgentRunner(agent_name=payload.agent_name, db_session=db)
        result = await runner.run(payload.message)
        return ChatResponse(**result)
    """
    # ── PLACEHOLDER — replace during sprint ───────────────────────────────────
    return ChatResponse(
        response=(
            f"[AgentShield] Received: '{payload.message}'. "
            "AI agent integration will be live on Nov 21. "
            "Use the Demo Center to test the security engine now."
        ),
        decision=None,
        risk_score=None,
    )


@router.get("/stream")
async def chat_stream(message: str, agent_name: str = "agent_payment", db: Session = Depends(get_db)):
    """
    LIVE BUILD: streaming SSE endpoint.

    On Nov 21, replace body with:
        from ai_agent import AgentRunner
        runner = AgentRunner(agent_name=agent_name, db_session=db)
        async def generate():
            async for chunk in runner.stream_run(message):
                yield f"data: {chunk}\n\n"
        return StreamingResponse(generate(), media_type="text/event-stream")
    """
    async def placeholder():
        yield f"data: AgentShield stream ready for Nov 21 sprint.\n\n"

    return StreamingResponse(placeholder(), media_type="text/event-stream")

