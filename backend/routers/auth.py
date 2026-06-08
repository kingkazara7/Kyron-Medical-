from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
import asyncio
from database import get_db
from models import Provider, AuditLog
from auth import verify_password, create_token, get_current_provider
import session_events

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    provider_id: int
    name: str
    role: str
    email: str


@router.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    provider = db.query(Provider).filter(Provider.email == req.email).first()
    if not provider or not verify_password(req.password, provider.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not provider.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    # Phase 1: if other sessions are open, signal them to flush unsaved drafts.
    # Their token is still valid at this point so the draft save will succeed.
    if session_events.has_connections(provider.id):
        await session_events.notify_event(provider.id, "flush")
        # Grace period: allow the draft save round-trip to complete
        await asyncio.sleep(1.5)

    # Phase 2: invalidate all existing sessions
    provider.session_version = (provider.session_version or 0) + 1
    token = create_token({"sub": str(provider.id), "role": provider.role.value, "sv": provider.session_version})

    db.add(AuditLog(
        actor_id=provider.id,
        action="login",
        target_type="provider",
        target_id=provider.id,
        extra={"email": provider.email},
    ))
    db.commit()

    # Phase 3: notify existing connections that they are now superseded
    await session_events.notify_event(provider.id, "superseded")

    return LoginResponse(
        access_token=token,
        provider_id=provider.id,
        name=f"{provider.first_name} {provider.last_name}",
        role=provider.role.value,
        email=provider.email,
    )


@router.get("/me")
def me(current: Provider = Depends(get_current_provider)):
    return {
        "id": current.id,
        "name": f"{current.first_name} {current.last_name}",
        "email": current.email,
        "role": current.role.value,
    }


@router.get("/session-stream")
async def session_stream(current: Provider = Depends(get_current_provider)):
    """
    Long-lived SSE endpoint. The client connects once after login and holds
    the connection open. When another device logs in with the same account,
    this stream receives "flush" (save draft now) then "superseded" (session ended).
    A keepalive comment is sent every 25 s to prevent nginx from closing the connection.
    """
    q = session_events.register_queue(current.id)

    async def generate():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=25)
                    yield f"data: {event}\n\n"
                    if event == "superseded":
                        break  # Close stream — client will handle the rest
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"  # Prevents nginx from timing out
        finally:
            session_events.unregister_queue(current.id, q)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # Disable nginx response buffering for SSE
            "Connection": "keep-alive",
        },
    )
