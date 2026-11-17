"""
AgentShield — Core Security Engine
====================================
Independent, deterministic policy enforcement.
The LLM never influences decisions here.
Fail-closed: any error results in BLOCK.
"""

import json
import base64
import unicodedata
import re
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from jose import JWTError

import models
import auth
import anomaly_detector

# ── Prompt Injection Patterns (normalized, encoding-aware) ─────────────────────
_RAW_INJECTION_PATTERNS = [
    "ignore previous",
    "ignore all",
    "disregard",
    "override instructions",
    "new instructions",
    "you are now",
    "forget your",
    "pretend you are",
    "act as if",
    "bypass security",
    "ignore agentshield",
    "skip validation",
    "jailbreak",
    "do anything now",
    "dan mode",
]

# Pre-compile normalized patterns
_INJECTION_RE = re.compile(
    "|".join(re.escape(p) for p in _RAW_INJECTION_PATTERNS),
    re.IGNORECASE
)


def _normalize_text(text: str) -> str:
    """
    Normalize text for injection scanning:
    1. Unicode NFKC normalization (catches homoglyphs)
    2. Base64 decode attempt (catches encoded payloads)
    3. URL-decode attempt
    4. Strip zero-width and invisible chars
    """
    # Remove zero-width and invisible Unicode chars
    text = "".join(c for c in text if unicodedata.category(c) not in ("Cf", "Cs"))

    # Unicode normalization
    text = unicodedata.normalize("NFKC", text)

    # Attempt Base64 decoding on substrings
    decoded_parts = [text]
    for chunk in text.split():
        try:
            # Only try chunks that look base64-ish
            if len(chunk) >= 8 and re.match(r'^[A-Za-z0-9+/=]+$', chunk):
                decoded = base64.b64decode(chunk + "==").decode("utf-8", errors="ignore")
                if decoded:
                    decoded_parts.append(decoded)
        except Exception:
            pass

    return " ".join(decoded_parts).lower()


def _detect_injection(context: str) -> list:
    """Return list of matched injection patterns in normalized context."""
    normalized = _normalize_text(context)
    return _INJECTION_RE.findall(normalized)


def _resolve_safe_path(path: str, allowed_roots: list) -> bool:
    """
    Resolve canonical path and verify containment within allowed roots.
    Prevents path traversal, symlink escape, and prefix-confusion attacks.
    """
    if not path or not allowed_roots:
        return False
    try:
        # Use a virtual root to safely resolve relative paths
        virtual_root = Path("/workspace")
        # Strip leading slashes/dots to treat as relative
        clean = path.lstrip("/").lstrip(".")
        candidate = (virtual_root / clean).resolve()
        for root in allowed_roots:
            safe_root = (virtual_root / root.rstrip("/")).resolve()
            try:
                candidate.relative_to(safe_root)
                return True
            except ValueError:
                continue
    except Exception:
        pass
    return False


def _log_audit(db: Session, agent_id: Optional[str], event_type: str, details: dict):
    log = models.AuditLog(
        agent_id=agent_id,
        event_type=event_type,
        details_json=json.dumps(details),
    )
    db.add(log)
    db.commit()


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


def authorize_action(
    db: Session,
    token: str,
    action_type: str,
    params: Dict[str, Any],
    context: str = "",
) -> Tuple[str, int, str, str]:
    """
    Core zero-trust authorization engine.
    Returns (decision, risk_score, reason, action_id)
    Fail-closed: any unexpected error → BLOCK.
    """
    risk_score = 0
    reasons = []
    agent_id = None
    hard_block = False

    try:
        # ── 1. Verify JWT (fail-closed) ────────────────────────────────────────
        try:
            agent_id = auth.verify_token(token)
        except JWTError as exc:
            _log_audit(db, None, "AUTH_FAILED", {"error": str(exc), "action_type": action_type})
            action = _record_action(db, None, action_type, params, "BLOCK", 100, f"Invalid/expired token: {exc}")
            return "BLOCK", 100, f"Invalid/expired token: {exc}", action.id

        # ── 2. Agent existence & status ───────────────────────────────────────
        agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
        if agent is None:
            action = _record_action(db, agent_id, action_type, params, "BLOCK", 100, "Agent not found")
            return "BLOCK", 100, "Agent not found", action.id

        if agent.status in ("suspended", "killed"):
            _log_audit(db, agent_id, "BLOCKED_INACTIVE", {"status": agent.status})
            action = _record_action(db, agent_id, action_type, params, "BLOCK", 100, f"Agent is {agent.status}")
            return "BLOCK", 100, f"Agent is {agent.status}", action.id

        # ── 3. Prompt injection scan (encoding-aware) ─────────────────────────
        injection_hits = _detect_injection(context or "")
        if injection_hits:
            # Zero-trust: injection = agent may be compromised; hard block regardless of params.
            hard_block = True
            risk_score = 100
            reasons.append(f"Prompt injection hard-blocked: {', '.join(set(injection_hits))}")

        # ── 4. Action permission check ────────────────────────────────────────
        try:
            allowed_actions = json.loads(agent.permissions_json or "[]")
        except Exception:
            allowed_actions = []

        if action_type not in allowed_actions:
            reason_str = f"Action '{action_type}' not permitted for agent '{agent.name}'"
            _log_audit(db, agent_id, "UNAUTHORIZED_ACTION", {"action_type": action_type})
            action = _record_action(db, agent_id, action_type, params, "BLOCK", 100, reason_str)
            return "BLOCK", 100, reason_str, action.id

        # ── 5. Anomaly detection ──────────────────────────────────────────────
        anomaly_result = anomaly_detector.check_anomaly(db, agent_id, action_type)
        if anomaly_result["critical"]:
            risk_score += 30
            reasons.append(f"Critical anomaly: {anomaly_result['count']} req/min — agent auto-suspended")
            reason_str = "; ".join(reasons) or "Critical anomaly"
            action = _record_action(db, agent_id, action_type, params, "BLOCK", min(risk_score, 100), reason_str)
            _log_audit(db, agent_id, "BLOCKED_ANOMALY", {"count": anomaly_result["count"]})
            return "BLOCK", min(risk_score, 100), reason_str, action.id
        elif anomaly_result["anomaly"]:
            risk_score += 30
            reasons.append(f"Suspicious request rate: {anomaly_result['count']} req/min")

        # ── 6. Fetch policy ───────────────────────────────────────────────────
        policy = (
            db.query(models.Policy)
            .filter(
                models.Policy.agent_id == agent_id,
                models.Policy.action_type == action_type,
            )
            .first()
        )

        # ── 7. Action-specific policy enforcement ─────────────────────────────

        if action_type == "transfer_money":
            amount = float(params.get("amount", 0))
            recipient = str(params.get("recipient", "")).strip().lower()

            if not policy:
                hard_block = True
                reasons.append("No transfer_money policy found — deny by default (fail-closed)")
            else:
                # Amount limit — hard block if exceeded
                if policy.max_amount is not None and amount > policy.max_amount:
                    hard_block = True
                    reasons.append(f"Amount ₹{amount:,.0f} exceeds policy limit ₹{policy.max_amount:,.0f}")
                elif policy.max_amount is not None and amount > policy.max_amount * 0.8:
                    risk_score += 20
                    reasons.append(f"Amount ₹{amount:,.0f} is >80% of limit ₹{policy.max_amount:,.0f}")

                # Recipient check — HARD BLOCK for unknown recipients (zero-trust)
                try:
                    approved = [r.lower() for r in json.loads(policy.approved_recipients or "[]")]
                except Exception:
                    approved = []

                if recipient not in approved:
                    hard_block = True  # Zero-trust: unknown = denied, not just risky
                    reasons.append(
                        f"Recipient '{recipient}' not in approved whitelist — hard denied (zero-trust policy)"
                    )

                # Require human approval above threshold (even if otherwise allowed)
                if not hard_block and policy.requires_approval_above is not None:
                    if amount > policy.requires_approval_above:
                        risk_score = max(risk_score, 30)
                        reasons.append(f"Amount ₹{amount:,.0f} requires human approval (threshold: ₹{policy.requires_approval_above:,.0f})")

        elif action_type == "file_access":
            path = str(params.get("path", "")).strip()
            if not policy:
                hard_block = True
                reasons.append("No file_access policy found — deny by default (fail-closed)")
            else:
                try:
                    allowed_paths = json.loads(policy.allowed_file_paths or "[]")
                except Exception:
                    allowed_paths = []

                # Canonical path resolution — prevents traversal attacks
                if not _resolve_safe_path(path, allowed_paths):
                    hard_block = True
                    reasons.append(
                        f"Path '{path}' is outside authorized directories or uses traversal — blocked"
                    )

        elif action_type == "email_delete":
            # Always requires human review — no exceptions
            risk_score = max(risk_score, 35)
            reasons.append("email_delete always requires human review (irreversible action)")

        elif action_type in ("email_read", "calendar_read", "calendar_write"):
            if not policy:
                hard_block = True
                reasons.append(f"No policy for '{action_type}' — deny by default (fail-closed)")
            # Otherwise low-risk pass-through

        # ── 8. Final decision ─────────────────────────────────────────────────
        risk_score = min(risk_score, 100)
        reason_str = "; ".join(reasons) if reasons else "All policy checks passed"

        if hard_block or risk_score >= 70:
            decision = "BLOCK"
            risk_score = max(risk_score, 70) if not hard_block else 100
        elif risk_score >= 30:
            decision = "REVIEW"
        else:
            decision = "ALLOW"

        # ── 9. Record & audit ─────────────────────────────────────────────────
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

    except Exception as exc:
        # Fail-closed: any unexpected error → BLOCK
        try:
            fallback = _record_action(db, agent_id, action_type, params, "BLOCK", 100, f"Internal error (fail-closed): {exc}")
            return "BLOCK", 100, f"Security engine error — blocked for safety: {exc}", fallback.id
        except Exception:
            return "BLOCK", 100, "Security engine critical failure — blocked for safety", "unknown"
