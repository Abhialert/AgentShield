import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import models


WINDOW_SECONDS = 60
SUSPICIOUS_THRESHOLD = 10
CRITICAL_THRESHOLD = 20


def check_anomaly(db: Session, agent_id: str, action_type: str) -> dict:
    """
    Track request rate for an agent over a 60-second rolling window.
    Returns {"anomaly": bool, "critical": bool, "count": int}
    """
    now = datetime.utcnow()
    window_start = now - timedelta(seconds=WINDOW_SECONDS)

    # Fetch existing window entry within the last 60 seconds
    tracker = (
        db.query(models.RateTracking)
        .filter(
            models.RateTracking.agent_id == agent_id,
            models.RateTracking.action_type == action_type,
            models.RateTracking.window_start >= window_start,
        )
        .order_by(models.RateTracking.window_start.desc())
        .first()
    )

    if tracker is None:
        # Create new window
        tracker = models.RateTracking(
            agent_id=agent_id,
            action_type=action_type,
            window_start=now,
            count=1,
        )
        db.add(tracker)
        db.commit()
        return {"anomaly": False, "critical": False, "count": 1}

    tracker.count += 1
    db.commit()

    count = tracker.count
    anomaly = count > SUSPICIOUS_THRESHOLD
    critical = count > CRITICAL_THRESHOLD

    if critical:
        # Auto-suspend the agent
        agent = db.query(models.Agent).filter(models.Agent.id == agent_id).first()
        if agent and agent.status == "active":
            agent.status = "suspended"
            db.commit()
            # Log the auto-suspension
            log = models.AuditLog(
                agent_id=agent_id,
                event_type="AUTO_SUSPENDED",
                details_json=json.dumps({
                    "reason": "Critical anomaly: >20 actions/minute",
                    "count": count,
                    "action_type": action_type,
                }),
            )
            db.add(log)
            db.commit()

    return {"anomaly": anomaly, "critical": critical, "count": count}
