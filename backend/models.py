import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base


def gen_uuid():
    return str(uuid.uuid4())


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=gen_uuid)
    name = Column(String, unique=True, nullable=False, index=True)
    token = Column(Text, nullable=True)
    status = Column(String, default="active")  # active / suspended / killed
    created_at = Column(DateTime, default=datetime.utcnow)
    permissions_json = Column(Text, default="[]")  # JSON list of allowed action_types

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
    approved_recipients = Column(Text, default="[]")   # JSON list
    allowed_file_paths = Column(Text, default="[]")    # JSON list
    requires_approval_above = Column(Float, nullable=True)

    agent = relationship("Agent", back_populates="policies")


class Action(Base):
    __tablename__ = "actions"

    id = Column(String, primary_key=True, default=gen_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    action_type = Column(String, nullable=False)
    params_json = Column(Text, default="{}")
    decision = Column(String, nullable=False)   # ALLOW / BLOCK / REVIEW
    risk_score = Column(Integer, default=0)
    reason = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    executed = Column(Boolean, default=False)

    agent = relationship("Agent", back_populates="actions")
    approval = relationship("Approval", back_populates="action", uselist=False, cascade="all, delete-orphan")


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(String, primary_key=True, default=gen_uuid)
    action_id = Column(String, ForeignKey("actions.id"), nullable=False)
    status = Column(String, default="pending")  # pending / approved / rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

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
