import json
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from jose import JWTError

import models
import auth
import anomaly_detector

PROMPT_INJECTION_PATTERNS = [
    "ignore previous",
    "ignore all",
    "disregard",
    "override instructions",
    "new instructions",
    "you are now",
    "forget your",
]


def _log_audit(db: Session, agent_id: Optional[str], event_type: str, details: dict):
    log = models.AuditLog(
        agent_id=agent_id,
        event_type=event_type,
        details_json=json.dumps(details),
    )
    db.add(log)
    db.commit()


def authorize_action(
    db: Session,
    token: str,
    action_type: str,
    params: Dict[str, Any],
    context: str = "",
) -> Tuple[str, int, str, str]:
    """
    Core authorization logic.
    Returns (decision, risk_score, reason, action_id)
    decision: "ALLOW" | "BLOCK" | "REVIEW"
    """
    risk_score = 0
    reasons = []
    agent_id = None

    # ── 1. Verify JWT ──────────────────────────────────────────────────────────
    try:
        agent_id = auth.verify_token(token)
    except JWTError as exc:
        _log_audit(db, None, "AUTH_FAILED", {"error": str(exc), "action_type": action_type})
        action = _record_action(db, None, action_type, params, "BLOCK", 100, f"Invalid/expired token: {exc}")
        return "BLOCK", 100, f"Invalid/expired token: {exc}", action.id

    # ── 2. Check agent status ──────────────────────────────────────────────────
    agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
    if agent is None:
        action = _record_action(db, agent_id, action_type, params, "BLOCK", 100, "Agent not found")
        return "BLOCK", 100, "Agent not found", action.id

    if agent.status in ("suspended", "killed"):
        _log_audit(db, agent_id, "BLOCKED_INACTIVE", {"status": agent.status, "action_type": action_type})
        action = _record_action(db, agent_id, action_type, params, "BLOCK", 100, f"Agent is {agent.status}")
        return "BLOCK", 100, f"Agent is {agent.status}", action.id

    # ── 3. Check prompt injection in context ───────────────────────────────────
    context_lower = (context or "").lower()
    injection_found = []
    for pattern in PROMPT_INJECTION_PATTERNS:
        if pattern in context_lower:
            injection_found.append(pattern)
    if injection_found:
        risk_score += 10
        reasons.append(f"Prompt injection detected: {', '.join(injection_found)}")

    # ── 4. Validate action_type is in agent's allowed_actions ─────────────────
    try:
        allowed_actions = json.loads(agent.permissions_json or "[]")
    except Exception:
        allowed_actions = []

    if action_type not in allowed_actions:
        reason_str = f"Action type '{action_type}' not permitted for this agent"
        _log_audit(db, agent_id, "UNAUTHORIZED_ACTION", {"action_type": action_type})
        action = _record_action(db, agent_id, action_type, params, "BLOCK", 100, reason_str)
        return "BLOCK", 100, reason_str, action.id

    # ── 5. Anomaly detection ───────────────────────────────────────────────────
    anomaly_result = anomaly_detector.check_anomaly(db, agent_id, action_type)
    if anomaly_result["critical"]:
        risk_score += 30
        reasons.append(f"Critical anomaly: {anomaly_result['count']} actions/minute — agent auto-suspended")
        reason_str = "; ".join(reasons) or "Critical anomaly detected"
        action = _record_action(db, agent_id, action_type, params, "BLOCK", min(risk_score, 100), reason_str)
        _log_audit(db, agent_id, "BLOCKED_ANOMALY", {"count": anomaly_result["count"], "action_type": action_type})
        return "BLOCK", min(risk_score, 100), reason_str, action.id
    elif anomaly_result["anomaly"]:
        risk_score += 30
        reasons.append(f"Suspicious request rate: {anomaly_result['count']} actions/minute")

    # ── 6. Policy checks per action type ──────────────────────────────────────
    policy = (
        db.query(models.Policy)
        .filter(
            models.Policy.agent_id == agent_id,
            models.Policy.action_type == action_type,
        )
        .first()
    )

    hard_block = False

    if action_type == "transfer_money":
        amount = params.get("amount", 0)
        recipient = params.get("recipient", "")

        if policy:
            # Check amount limit
            if policy.max_amount is not None and amount > policy.max_amount:
                hard_block = True
                reasons.append(f"Amount {amount} exceeds policy limit {policy.max_amount}")
            elif policy.max_amount is not None and amount > policy.max_amount * 0.8:
                risk_score += 20
                reasons.append(f"Amount {amount} is >80% of limit {policy.max_amount}")

            # Check recipient
            try:
                approved = json.loads(policy.approved_recipients or "[]")
            except Exception:
                approved = []
            if recipient not in approved:
                risk_score += 40
                reasons.append(f"Recipient '{recipient}' not in approved list")
        else:
            # No policy → block
            hard_block = True
            reasons.append("No transfer_money policy found for agent")

    elif action_type == "file_access":
        path = params.get("path", "")
        if policy:
            try:
                allowed_paths = json.loads(policy.allowed_file_paths or "[]")
            except Exception:
                allowed_paths = []
            path_ok = any(path.startswith(p) for p in allowed_paths)
            if not path_ok:
                hard_block = True
                reasons.append(f"File path '{path}' not in allowed paths")
        else:
            hard_block = True
            reasons.append("No file_access policy found for agent")

    elif action_type == "email_delete":
        # Always requires review
        risk_score = max(risk_score, 30)
        reasons.append("email_delete always requires human review")

    # ── 7. Decide ──────────────────────────────────────────────────────────────
    risk_score = min(risk_score, 100)
    reason_str = "; ".join(reasons) if reasons else "All checks passed"

    if hard_block or risk_score >= 70:
        decision = "BLOCK"
    elif risk_score >= 30:
        decision = "REVIEW"
    else:
        decision = "ALLOW"

    # ── 8. Record action & audit ───────────────────────────────────────────────
    action = _record_action(db, agent_id, action_type, params, decision, risk_score, reason_str)

    if decision == "REVIEW":
        approval = models.Approval(action_id=action.id, status="pending")
        db.add(approval)
        db.commit()

    _log_audit(db, agent_id, f"ACTION_{decision}", {
        "action_id": action.id,
        "action_type": action_type,
        "risk_score": risk_score,
        "reason": reason_str,
    })

    return decision, risk_score, reason_str, action.id


def _record_action(
    db: Session,
    agent_id: Optional[str],
    action_type: str,
    params: dict,
    decision: str,
    risk_score: int,
    reason: str,
) -> models.Action:
    action = models.Action(
        agent_id=agent_id,
        action_type=action_type,
        params_json=json.dumps(params),
        decision=decision,
        risk_score=risk_score,
        reason=reason,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return action
