import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, unique=True, nullable=False, index=True)
    token = Column(Text, nullable=True)        # Raw JWT stored internally for gateway use; NEVER returned by API
    token_hash = Column(Text, nullable=True)   # SHA-256 hash for verification without exposing raw token
    status = Column(String, default="active")  # active / suspended / killed
    created_at = Column(DateTime, default=datetime.utcnow)
    permissions_json = Column(Text, default="[]")

    policies = relationship("Policy", back_populates="agent", cascade="all, delete-orphan")
    actions = relationship("Action", back_populates="agent", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="agent", cascade="all, delete-orphan")
    rate_tracking = relationship("RateTracking", back_populates="agent", cascade="all, delete-orphan")


class Policy(Base):
    __tablename__ = "policies"

    id = Column(String, primary_key=True, default=gen_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    action_type = Column(String, nullable=False)
    max_amount = Column(Float, nullable=True)
    approved_recipients = Column(Text, default="[]")
    allowed_file_paths = Column(Text, default="[]")
    requires_approval_above = Column(Float, nullable=True)

    agent = relationship("Agent", back_populates="policies")


class Action(Base):
    __tablename__ = "actions"

    id = Column(String, primary_key=True, default=gen_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=True)   # nullable: auth-fail BLOCK still recorded
    action_type = Column(String, nullable=False)
    params_json = Column(Text, default="{}")
    decision = Column(String, nullable=False)   # ALLOW / BLOCK / REVIEW
    risk_score = Column(Integer, default=0)
    reason = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    executed = Column(Boolean, default=False)

    agent = relationship("Agent", back_populates="actions")
    approval = relationship("Approval", back_populates="action", uselist=False, cascade="all, delete-orphan")
    execution_grant = relationship("ExecutionGrant", back_populates="action", uselist=False, cascade="all, delete-orphan")


class ExecutionGrant(Base):
    """
    Persistent, atomic single-use execution grant.
    Replaces the in-memory _used_grants set:
    - Survives server restarts
    - Multi-worker safe (atomic DB update pattern)
    - Prevents replay attacks via consumed_at field
    """
    __tablename__ = "execution_grants"

    id = Column(String, primary_key=True, default=gen_uuid)
    action_id = Column(String, ForeignKey("actions.id"), nullable=False, unique=True)
    jti = Column(String, nullable=False, unique=True)   # JWT ID from grant token — unique index
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime, nullable=True)       # None = not yet used

    action = relationship("Action", back_populates="execution_grant")

    __table_args__ = (
        UniqueConstraint("jti", name="uq_execution_grant_jti"),
    )


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(String, primary_key=True, default=gen_uuid)
    action_id = Column(String, ForeignKey("actions.id"), nullable=False)
    status = Column(String, default="pending")  # pending / approved / rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    execution_result = Column(Text, nullable=True)   # JSON result from executor after approved exec

    action = relationship("Action", back_populates="approval")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=gen_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    event_type = Column(String, nullable=False)
    details_json = Column(Text, default="{}")
    created_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("Agent", back_populates="audit_logs")


class RateTracking(Base):
    __tablename__ = "rate_tracking"

    id = Column(String, primary_key=True, default=gen_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    action_type = Column(String, nullable=False)
    window_start = Column(DateTime, nullable=False)
    count = Column(Integer, default=0)

    agent = relationship("Agent", back_populates="rate_tracking")
