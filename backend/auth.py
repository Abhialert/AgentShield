from datetime import datetime, timedelta
from typing import List, Optional
from jose import JWTError, jwt

SECRET_KEY = "agentshield-secret-2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24 * 365  # 1 year for hackathon agents


def create_agent_token(agent_id: str, permissions: List[str]) -> str:
    """Create a JWT token for an agent."""
    expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": agent_id,
        "permissions": permissions,
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "agent",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[str]:
    """
    Verify a JWT token and return the agent_id (sub).
    Raises JWTError if invalid or expired.
    """
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    agent_id: str = payload.get("sub")
    if agent_id is None:
        raise JWTError("Token missing subject")
    return agent_id


def get_token_permissions(token: str) -> List[str]:
    """Extract permissions list from token without raising on missing sub."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload.get("permissions", [])
