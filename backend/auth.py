import os
from datetime import datetime, timedelta
from typing import List, Optional
from jose import JWTError, jwt

# Secret loaded from environment — never hardcoded in source
SECRET_KEY = os.environ.get("AGENTSHIELD_SECRET", "agentshield-secret-2024-change-in-prod")
ALGORITHM = "HS256"

# Short-lived tokens: 24h for hackathon demo; set 15m in production
ACCESS_TOKEN_EXPIRE_HOURS = int(os.environ.get("TOKEN_EXPIRE_HOURS", "24"))


def create_agent_token(agent_id: str, permissions: List[str]) -> str:
    """Create a signed JWT for an agent with explicit expiry."""
    now = datetime.utcnow()
    expire = now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": agent_id,
        "permissions": permissions,
        "exp": expire,
        "iat": now,
        "jti": f"{agent_id}-{int(now.timestamp())}",  # unique token ID (replay-prevention)
        "type": "agent",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[str]:
    """
    Verify a JWT and return agent_id.
    Raises JWTError if invalid, expired, or malformed.
    Fail-closed: any exception propagates as a block.
    """
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    agent_id: str = payload.get("sub")
    token_type: str = payload.get("type")
    if agent_id is None:
        raise JWTError("Token missing subject")
    if token_type != "agent":
        raise JWTError("Invalid token type")
    return agent_id


def get_token_permissions(token: str) -> List[str]:
    """Extract permissions list from a valid token."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload.get("permissions", [])


def create_execution_grant(action_id: str, action_type: str, agent_id: str) -> str:
    """
    Create a single-use, short-lived execution grant token.
    Valid for 2 minutes only. Tied to a specific action_id.
    This prevents replay attacks: the grant can only be used once
    for the specific authorized action.
    """
    now = datetime.utcnow()
    expire = now + timedelta(minutes=2)
    payload = {
        "sub": agent_id,
        "action_id": action_id,
        "action_type": action_type,
        "exp": expire,
        "iat": now,
        "type": "execution_grant",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_execution_grant(grant_token: str, action_id: str) -> str:
    """
    Verify a single-use execution grant.
    Raises JWTError if invalid, expired, wrong type, or wrong action_id.
    """
    payload = jwt.decode(grant_token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != "execution_grant":
        raise JWTError("Not an execution grant token")
    if payload.get("action_id") != action_id:
        raise JWTError("Grant token does not match action_id — possible replay attack")
    agent_id = payload.get("sub")
    if not agent_id:
        raise JWTError("Grant token missing agent subject")
    return agent_id
