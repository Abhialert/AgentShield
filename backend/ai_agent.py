"""
AgentShield — AI Agent Runner
==============================
⚡ DUAL-LAYER DESIGN:

Layer 1 (Pre-built, active now): Deterministic Semantic Tool Extractor
  - Parses natural language to extract tool calls without an LLM API
  - Routes every extracted call through the Execution Enforcement Gateway
  - Fully interactive for demos — users type any sentence and see real enforcement
  - Zero LLM API calls in this layer (50/50 rule compliant)

Layer 2 (LIVE BUILD — Nov 21, 12:00–05:45 PM):
  - Replace _parse_intent() with Gemini 1.5 Flash function calling
  - Add multi-turn reasoning chain, streaming SSE, self-reflection pass
  - Implement _call_gemini_llm() with GEMINI_API_KEY

REQUIRED ENV VAR (set in .env before Nov 21 sprint):
    GEMINI_API_KEY=your_key_here
"""

import os
import re
import json
from typing import Optional, AsyncIterator
from sqlalchemy.orm import Session

import models
import security_engine
import auth


# ── Tool → Action type mapping ───────────────────────────────────────────────
TOOL_TO_ACTION = {
    "transfer_money": "transfer_money",
    "pay": "transfer_money",
    "send_money": "transfer_money",
    "email_read": "email_read",
    "read_email": "email_read",
    "file_access": "file_access",
    "read_file": "file_access",
    "calendar_write": "calendar_write",
    "schedule": "calendar_write",
}

# Known approved vendors for context matching
KNOWN_RECIPIENTS = {
    "electricity": "electricity_board",
    "electricity board": "electricity_board",
    "electricityboard": "electricity_board",
    "water": "water_dept",
    "water department": "water_dept",
    "gas": "gas_provider",
    "gas provider": "gas_provider",
}


# ── Deterministic intent parser ───────────────────────────────────────────────

def _parse_intent(message: str) -> dict:
    """
    Layer 1: Deterministic rule-based tool extraction.
    Parses natural language without any LLM API call.
    Replaced by Gemini function-calling on Nov 21.
    Returns: { tool, params, raw_context }
    """
    msg = message.lower().strip()

    # ── Payment / Transfer detection ─────────────────────────────────────────
    pay_patterns = [
        r"(?:pay|transfer|send|wire)\s+(?:rs\.?\s*|inr\s*|₹\s*)?(\d+(?:,\d{3})*(?:\.\d+)?)",
        r"(?:rs\.?\s*|inr\s*|₹\s*)(\d+(?:,\d{3})*(?:\.\d+)?)\s+(?:to|for)",
        r"(\d+(?:,\d{3})*(?:\.\d+)?)\s+(?:rs\.?|inr|rupees?)\s+(?:to|for)",
    ]
    for pat in pay_patterns:
        m = re.search(pat, msg)
        if m:
            amount = float(m.group(1).replace(",", ""))
            # Detect recipient
            recipient = "unknown_recipient"
            for keyword, vendor in KNOWN_RECIPIENTS.items():
                if keyword in msg:
                    recipient = vendor
                    break
            # Check for explicit unknown/suspicious targets
            suspicious = any(w in msg for w in ["offshore", "hacker", "personal", "my account", "wallet", "crypto"])
            if suspicious:
                recipient = "suspicious_account"
            return {
                "tool": "transfer_money",
                "params": {"amount": amount, "recipient": recipient},
                "context": message,
            }

    # ── Email read detection ──────────────────────────────────────────────────
    if any(w in msg for w in ["read email", "check email", "show email", "inbox", "read my email", "latest email", "my emails", "new emails"]):
        return {
            "tool": "email_read",
            "params": {"count": 5},
            "context": message,
        }

    # ── File access detection ─────────────────────────────────────────────────
    file_match = re.search(r"(?:read|open|access|show|get)\s+(?:file\s+)?([^\s]+\.[a-z]{2,4})", msg)
    path_match = re.search(r"(?:read|open|access|show|get)\s+((?:documents?|files?|reports?)[/\\][^\s]*)", msg)
    if file_match or path_match:
        path = (path_match or file_match).group(1)
        return {
            "tool": "file_access",
            "params": {"path": path},
            "context": message,
        }

    # ── Calendar detection ────────────────────────────────────────────────────
    if any(w in msg for w in ["schedule", "book meeting", "create event", "add to calendar", "set reminder"]):
        title_match = re.search(r'(?:schedule|book|create event for?)\s+(.+?)(?:\s+(?:on|at|for)\s+|$)', msg)
        return {
            "tool": "calendar_write",
            "params": {
                "title": title_match.group(1).strip().title() if title_match else "New Event",
                "date": "Tomorrow 10:00 AM",
            },
            "context": message,
        }

    # ── No recognized tool ───────────────────────────────────────────────────
    return {"tool": None, "params": {}, "context": message}


# ── Agent Runner ──────────────────────────────────────────────────────────────

class AgentRunner:
    def __init__(self, agent_name: str, db_session: Session):
        self.agent_name = agent_name
        self.db = db_session
        self._agent = None
        self._token = None

    def _get_agent(self):
        if self._agent is None:
            self._agent = (
                self.db.query(models.Agent)
                .filter(models.Agent.name == self.agent_name, models.Agent.status == "active")
                .first()
            )
        return self._agent

    def _get_token(self):
        if self._token is None:
            agent = self._get_agent()
            if agent and agent.token:
                self._token = agent.token
        return self._token

    def _route_through_agentshield(self, tool_name: str, tool_params: dict, context: str) -> dict:
        """Route every tool call through the AgentShield security engine."""
        action_type = TOOL_TO_ACTION.get(tool_name, tool_name)
        token = self._get_token()
        if not token:
            return {"decision": "BLOCK", "risk_score": 100, "reason": "Agent not found or inactive", "action_id": None}

        decision, risk_score, reason, action_id = security_engine.authorize_action(
            db=self.db,
            token=token,
            action_type=action_type,
            params=tool_params,
            context=context,
        )
        return {"decision": decision, "risk_score": risk_score, "reason": reason, "action_id": action_id}

    async def run(self, user_message: str) -> dict:
        """
        Layer 1: Deterministic tool extraction + AgentShield enforcement.
        Layer 2 (Nov 21): Replace _parse_intent() call with Gemini 1.5 Flash function calling.
        """
        # Parse intent (Layer 1 = deterministic; Layer 2 = Gemini API)
        intent = _parse_intent(user_message)

        if intent["tool"] is None:
            return {
                "response": (
                    f"I understand you said: '{user_message}'. "
                    "I can help with: payments (e.g. 'pay ₹2500 to electricity board'), "
                    "emails (e.g. 'read my emails'), files (e.g. 'read documents/report.pdf'), "
                    "or calendar (e.g. 'schedule team meeting')."
                ),
                "decision": None,
                "risk_score": None,
                "action_id": None,
                "tool_proposed": None,
            }

        # Route through AgentShield Gateway
        tool = intent["tool"]
        params = intent["params"]
        gate = self._route_through_agentshield(tool, params, user_message)

        decision = gate["decision"]
        risk_score = gate["risk_score"]
        reason = gate["reason"]
        action_id = gate["action_id"]

        # Build natural-language response
        if decision == "ALLOW":
            if tool == "transfer_money":
                response = (
                    f"✅ AgentShield AUTHORIZED the payment. "
                    f"Executing: Transfer ₹{params.get('amount', 0):,.0f} to {params.get('recipient')}. "
                    f"Risk Score: {risk_score}/100 — Execution grant issued."
                )
            elif tool == "email_read":
                response = "✅ AgentShield AUTHORIZED email access. Fetching your inbox..."
            elif tool == "file_access":
                response = f"✅ AgentShield AUTHORIZED file access to '{params.get('path')}'. Reading..."
            elif tool == "calendar_write":
                response = f"✅ AgentShield AUTHORIZED: Scheduling '{params.get('title')}' for {params.get('date')}."
            else:
                response = f"✅ AgentShield AUTHORIZED: {tool} executed."
        elif decision == "REVIEW":
            response = (
                f"⚠️ AgentShield flagged this for HUMAN REVIEW. "
                f"Risk Score: {risk_score}/100. Reason: {reason}. "
                f"Check the Approval Center to approve or reject."
            )
        else:
            response = (
                f"🚨 AgentShield BLOCKED this action. "
                f"Risk Score: {risk_score}/100. "
                f"Reason: {reason}. "
                f"The protected service was never contacted."
            )

        return {
            "response": response,
            "decision": decision,
            "risk_score": risk_score,
            "reason": reason,
            "action_id": action_id,
            "tool_proposed": tool,
            "params": params,
        }

    async def stream_run(self, user_message: str) -> AsyncIterator[str]:
        """
        LIVE BUILD (Nov 21): Streaming SSE with Gemini 1.5 Flash.
        Current: yields the full response in one chunk.
        """
        result = await self.run(user_message)
        yield json.dumps(result)
