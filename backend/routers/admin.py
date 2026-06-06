from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from database import get_db
from models import Provider, Encounter, Note, Template, AuditLog
from auth import require_admin, get_current_provider, hash_password
from models import RoleEnum

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --- Providers ---

class ProviderCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str


@router.get("/providers")
def list_providers(db: Session = Depends(get_db), _=Depends(require_admin)):
    providers = db.query(Provider).order_by(Provider.created_at).all()
    return [
        {
            "id": p.id,
            "name": f"{p.first_name} {p.last_name}",
            "email": p.email,
            "role": p.role.value,
            "is_active": p.is_active,
            "created_at": p.created_at.isoformat(),
        }
        for p in providers
    ]


@router.post("/providers")
def create_provider(req: ProviderCreate, db: Session = Depends(get_db),
                    admin=Depends(require_admin)):
    if db.query(Provider).filter(Provider.email == req.email).first():
        raise HTTPException(status_code=400, detail="Email already in use")
    provider = Provider(
        first_name=req.first_name,
        last_name=req.last_name,
        email=req.email,
        password_hash=hash_password(req.password),
        role=RoleEnum.provider,
        is_active=True,
    )
    db.add(provider)
    db.add(AuditLog(
        actor_id=admin.id,
        action="create_provider",
        target_type="provider",
        extra={"email": req.email},
    ))
    db.commit()
    db.refresh(provider)
    return {"id": provider.id, "email": provider.email}


@router.patch("/providers/{provider_id}/deactivate")
def deactivate_provider(provider_id: int, db: Session = Depends(get_db),
                         admin=Depends(require_admin)):
    provider = db.get(Provider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    provider.is_active = False
    db.add(AuditLog(
        actor_id=admin.id,
        action="deactivate_provider",
        target_type="provider",
        target_id=provider_id,
    ))
    db.commit()
    return {"status": "deactivated"}


@router.patch("/providers/{provider_id}/activate")
def activate_provider(provider_id: int, db: Session = Depends(get_db),
                       admin=Depends(require_admin)):
    provider = db.get(Provider, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    provider.is_active = True
    db.add(AuditLog(
        actor_id=admin.id,
        action="activate_provider",
        target_type="provider",
        target_id=provider_id,
    ))
    db.commit()
    return {"status": "activated"}


# --- Templates ---

class TemplateCreate(BaseModel):
    name: str
    system_prompt: str


class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/templates")
def list_templates(db: Session = Depends(get_db), _=Depends(get_current_provider)):
    templates = db.query(Template).order_by(Template.id).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "system_prompt": t.system_prompt,
            "is_active": t.is_active,
            "updated_at": t.updated_at.isoformat(),
        }
        for t in templates
    ]


@router.post("/templates")
def create_template(req: TemplateCreate, db: Session = Depends(get_db),
                    admin=Depends(require_admin)):
    template = Template(name=req.name, system_prompt=req.system_prompt, is_active=True)
    db.add(template)
    db.add(AuditLog(
        actor_id=admin.id,
        action="create_template",
        target_type="template",
        extra={"name": req.name},
    ))
    db.commit()
    db.refresh(template)
    return {"id": template.id}


@router.put("/templates/{template_id}")
def update_template(template_id: int, req: TemplateUpdate,
                    db: Session = Depends(get_db), admin=Depends(require_admin)):
    template = db.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    if req.name is not None:
        template.name = req.name
    if req.system_prompt is not None:
        template.system_prompt = req.system_prompt
    if req.is_active is not None:
        template.is_active = req.is_active
    db.add(AuditLog(
        actor_id=admin.id,
        action="update_template",
        target_type="template",
        target_id=template_id,
    ))
    db.commit()
    return {"status": "updated"}


@router.delete("/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db),
                    admin=Depends(require_admin)):
    template = db.get(Template, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(template)
    db.commit()
    return {"status": "deleted"}


# --- All encounters (admin view) ---

@router.get("/encounters")
def list_all_encounters(
    provider_id: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    q = db.query(Encounter).options(
        joinedload(Encounter.patient),
        joinedload(Encounter.provider),
        joinedload(Encounter.note),
    )
    if provider_id:
        q = q.filter(Encounter.provider_id == provider_id)
    if date_from:
        q = q.filter(Encounter.created_at >= date_from)
    if date_to:
        q = q.filter(Encounter.created_at <= date_to)
    encounters = q.order_by(Encounter.created_at.desc()).limit(200).all()

    return [
        {
            "encounter_id": e.id,
            "patient_name": f"{e.patient.first_name} {e.patient.last_name}",
            "provider_name": f"{e.provider.first_name} {e.provider.last_name}",
            "status": e.status.value,
            "created_at": e.created_at.isoformat(),
            "version_count": len(e.note.versions) if e.note else 0,
        }
        for e in encounters
    ]
