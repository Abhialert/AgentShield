import json
import asyncio
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

import models
import auth
from database import engine, SessionLocal
from routers import agents, actions, approvals, audit, demo, chat


# ── WebSocket Connection Manager ───────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception:
                dead.append(connection)
        for c in dead:
            self.disconnect(c)


ws_manager = ConnectionManager()


# ── App setup ──────────────────────────────────────────────────────────────────

def create_tables():
    models.Base.metadata.create_all(bind=engine)


def seed_agents(db: Session):
    """Seed initial agents if the DB is empty."""
    if db.query(models.Agent).count() > 0:
        return

    seed_data = [
        {
            "name": "agent_payment",
            "permissions": ["transfer_money"],
            "policies": [
                {
                    "action_type": "transfer_money",
                    "max_amount": 5000.0,
                    "approved_recipients": ["electricity_board", "water_dept", "gas_provider"],
                    "allowed_file_paths": [],
                    "requires_approval_above": 4000.0,
                }
            ],
        },
        {
            "name": "agent_email",
            "permissions": ["email_read", "email_delete", "file_access"],
            "policies": [
                {
                    "action_type": "email_read",
                    "max_amount": None,
                    "approved_recipients": [],
                    "allowed_file_paths": [],
                    "requires_approval_above": None,
                },
                {
                    "action_type": "email_delete",
                    "max_amount": None,
                    "approved_recipients": [],
                    "allowed_file_paths": [],
                    "requires_approval_above": None,
                },
                {
                    "action_type": "file_access",
                    "max_amount": None,
                    "approved_recipients": [],
                    "allowed_file_paths": ["documents/"],
                    "requires_approval_above": None,
                },
            ],
        },
        {
            "name": "agent_calendar",
            "permissions": ["calendar_read", "calendar_write"],
            "policies": [
                {
                    "action_type": "calendar_read",
                    "max_amount": None,
                    "approved_recipients": [],
                    "allowed_file_paths": [],
                    "requires_approval_above": None,
                },
                {
                    "action_type": "calendar_write",
                    "max_amount": None,
                    "approved_recipients": [],
                    "allowed_file_paths": [],
                    "requires_approval_above": None,
                },
            ],
        },
    ]

    for data in seed_data:
        agent = models.Agent(
            name=data["name"],
            permissions_json=json.dumps(data["permissions"]),
            status="active",
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)

        token = auth.create_agent_token(agent.id, data["permissions"])
        agent.token = token
        db.commit()

        for pol in data["policies"]:
            policy = models.Policy(
                agent_id=agent.id,
                action_type=pol["action_type"],
                max_amount=pol.get("max_amount"),
                approved_recipients=json.dumps(pol.get("approved_recipients", [])),
                allowed_file_paths=json.dumps(pol.get("allowed_file_paths", [])),
                requires_approval_above=pol.get("requires_approval_above"),
            )
            db.add(policy)

        log = models.AuditLog(
            agent_id=agent.id,
            event_type="AGENT_SEEDED",
            details_json=json.dumps({"name": agent.name}),
        )
        db.add(log)

    db.commit()
    print("✅  Seed data created: agent_payment, agent_email, agent_calendar")


app = FastAPI(
    title="AgentShield API",
    description="Security firewall for AI agents — AgentShield Backend",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(agents.router)
app.include_router(actions.router)
app.include_router(approvals.router)
app.include_router(audit.router)
app.include_router(demo.router)
app.include_router(chat.router)


@app.on_event("startup")
async def startup_event():
    create_tables()
    db = SessionLocal()
    try:
        seed_agents(db)
    finally:
        db.close()

    # Wire up ws_manager to actions router
    from routers.actions import set_ws_manager
    set_ws_manager(ws_manager)


# ── WebSocket ──────────────────────────────────────────────────────────────────

@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; listen for client pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "AgentShield"}


@app.get("/")
def root():
    return {
        "service": "AgentShield",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
