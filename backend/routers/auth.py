from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import Provider, AuditLog
from auth import verify_password, create_token, get_current_provider

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
def login(req: LoginRequest, db: Session = Depends(get_db)):
    provider = db.query(Provider).filter(Provider.email == req.email).first()
    if not provider or not verify_password(req.password, provider.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not provider.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    token = create_token({"sub": str(provider.id), "role": provider.role.value})

    db.add(AuditLog(
        actor_id=provider.id,
        action="login",
        target_type="provider",
        target_id=provider.id,
        extra={"email": provider.email},
    ))
    db.commit()

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
