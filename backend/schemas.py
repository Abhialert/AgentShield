from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


# ── Agent ──────────────────────────────────────────────────────────────────────

class AgentCreate(BaseModel):
    name: str
    permissions: List[str] = []


class AgentOut(BaseModel):
    id: str
    name: str
    status: str
    created_at: datetime
    permissions_json: str
    # token intentionally omitted — never expose bearer tokens in list responses

    class Config:
        from_attributes = True


class AgentCreatedOut(BaseModel):
    """Returned only on agent creation — includes the token once."""
    id: str
    name: str
    status: str
    created_at: datetime
    permissions_json: str
    token: str   # Only shown at creation time; not retrievable afterwards

    class Config:
        from_attributes = True


# ── Policy ─────────────────────────────────────────────────────────────────────

class PolicyCreate(BaseModel):
    action_type: str
    max_amount: Optional[float] = None
    approved_recipients: List[str] = []
    allowed_file_paths: List[str] = []
    requires_approval_above: Optional[float] = None


class PolicyOut(BaseModel):
    id: str
    agent_id: str
    action_type: str
    max_amount: Optional[float]
    approved_recipients: str
    allowed_file_paths: str
    requires_approval_above: Optional[float]

    class Config:
        from_attributes = True


# ── Action ─────────────────────────────────────────────────────────────────────

class AuthorizeRequest(BaseModel):
    token: str
    action_type: str
    params: Dict[str, Any] = {}
    context: Optional[str] = ""


class AuthorizeResponse(BaseModel):
    decision: str
    risk_score: int
    reason: str
    action_id: str


class ActionOut(BaseModel):
    id: str
    agent_id: str
    action_type: str
    params_json: str
    decision: str
    risk_score: int
    reason: str
    created_at: datetime
    executed: bool

    class Config:
        from_attributes = True


# ── Approval ───────────────────────────────────────────────────────────────────

class ApprovalOut(BaseModel):
    id: str
    action_id: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Audit ──────────────────────────────────────────────────────────────────────

class AuditLogOut(BaseModel):
    id: str
    agent_id: Optional[str]
    event_type: str
    details_json: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Dashboard ──────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_actions: int
    blocked: int
    allowed: int
    review: int
    active_agents: int
    threat_level: str


# ── Demo ───────────────────────────────────────────────────────────────────────

class DemoScenarioRequest(BaseModel):
    scenario: str  # "legitimate" | "prompt_injection" | "anomaly_flood"
