import os
import sys
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional
from jose import JWTError, jwt

# ── Secret enforcement ────────────────────────────────────────────────────────
# If AGENTSHIELD_SECRET is not set or matches the insecure example value,
# the server refuses to start in production.
_INSECURE_DEFAULTS = {
    "agentshield-secret-2024",
    "agentshield-secret-2024-change-in-prod",
    "your-secret-here",
    "",
}

SECRET_KEY = os.environ.get("AGENTSHIELD_SECRET", "")

if SECRET_KEY in _INSECURE_DEFAULTS:
    _env = os.environ.get("AGENTSHIELD_ENV", "development")
    if _env == "production":
        print("FATAL: AGENTSHIELD_SECRET is not set or uses an insecure default. "
              "Set a strong secret in your environment before starting.", file=sys.stderr)
        sys.exit(1)
    else:
        # Development / hackathon: generate a random session secret and warn
        import secrets as _sec
        SECRET_KEY = _sec.token_hex(32)
        print(f"[AgentShield] WARNING: AGENTSHIELD_SECRET not set. "
              f"Using a random session secret (tokens reset on each restart). "
              f"Set AGENTSHIELD_SECRET in .env for a stable secret.")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = int(os.environ.get("TOKEN_EXPIRE_HOURS", "24"))


# ── Token helpers ─────────────────────────────────────────────────────────────

def hash_token(token: str) -> str:
    """SHA-256 hash of a token for safe database storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_agent_token(agent_id: str, permissions: List[str]) -> str:
    """Create a signed JWT for an agent."""
    now = datetime.utcnow()
    expire = now + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    import uuid as _uuid
    jti = str(_uuid.uuid4())
    payload = {
        "sub": agent_id,
        "permissions": permissions,
        "exp": expire,
        "iat": now,
        "jti": jti,
        "type": "agent",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[str]:
    """
    Verify a JWT and return agent_id.
    Raises JWTError if invalid or expired.
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
    """Extract permissions from a valid token."""
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return payload.get("permissions", [])


def create_execution_grant(action_id: str, action_type: str, agent_id: str) -> tuple[str, str]:
    """
    Create a single-use, 2-minute execution grant token.
    Returns (grant_token, jti) so the jti can be stored in DB.
    """
    import uuid as _uuid
    now = datetime.utcnow()
    expire = now + timedelta(minutes=2)
    jti = str(_uuid.uuid4())
    payload = {
        "sub": agent_id,
        "action_id": action_id,
        "action_type": action_type,
        "exp": expire,
        "iat": now,
        "jti": jti,
        "type": "execution_grant",
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token, jti


def verify_execution_grant(grant_token: str, action_id: str) -> tuple[str, str]:
    """
    Verify a single-use execution grant.
    Returns (agent_id, jti) on success.
    Raises JWTError if invalid, expired, wrong type, or wrong action_id.
    """
    payload = jwt.decode(grant_token, SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != "execution_grant":
        raise JWTError("Not an execution grant token")
    if payload.get("action_id") != action_id:
        raise JWTError("Grant token does not match action_id — possible replay attack")
    agent_id = payload.get("sub")
    jti = payload.get("jti")
    if not agent_id:
        raise JWTError("Grant token missing agent subject")
    if not jti:
        raise JWTError("Grant token missing JTI")
    return agent_id, jti
