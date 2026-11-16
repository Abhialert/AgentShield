"""
AgentShield — Behavioral Anomaly Detector
==========================================
Sliding-window, timestamp-based rate tracking.
Detects burst attacks across window boundaries accurately.
"""

import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import models

WINDOW_SECONDS = 60
SUSPICIOUS_THRESHOLD = 10   # > 10 req/min → suspicious
CRITICAL_THRESHOLD = 20     # > 20 req/min → auto-suspend


def check_anomaly(db: Session, agent_id: str, action_type: str) -> dict:
    """
    Sliding-window anomaly detection using timestamped events.
    Counts all events for this agent+action_type within the last WINDOW_SECONDS.
    Uses timestamp-based counting — never stale counter confusion.
    """
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=WINDOW_SECONDS)

    # Count real events in the sliding window (not a stale counter)
    recent_count = (
        db.query(models.RateTracking)
        .filter(
            models.RateTracking.agent_id == agent_id,
            models.RateTracking.action_type == action_type,
            models.RateTracking.window_start >= window_start,
        )
        .count()
    )

    # Record this new event as its own timestamp row
    event = models.RateTracking(
        agent_id=agent_id,
        action_type=action_type,
        window_start=now,
        count=1,  # each row = 1 event at that timestamp
    )
    db.add(event)
    db.commit()

    # +1 for the event we just recorded
    total_in_window = recent_count + 1

    anomaly = total_in_window > SUSPICIOUS_THRESHOLD
    critical = total_in_window > CRITICAL_THRESHOLD

    if critical:
        agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
        if agent and agent.status == "active":
            agent.status = "suspended"
            db.commit()
            log = models.AuditLog(
                agent_id=agent_id,
                event_type="AUTO_SUSPENDED",
                details_json=json.dumps({
                    "reason": f"Critical anomaly: {total_in_window} requests in {WINDOW_SECONDS}s window",
                    "count": total_in_window,
                    "action_type": action_type,
                    "window_seconds": WINDOW_SECONDS,
                }),
            )
            db.add(log)
            db.commit()

    return {
        "anomaly": anomaly,
        "critical": critical,
        "count": total_in_window,
        "window_seconds": WINDOW_SECONDS,
    }
