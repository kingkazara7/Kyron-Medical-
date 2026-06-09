from datetime import date
from typing import Optional
from services.ai import has_clinical_content
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from database import get_db
from models import Provider, Encounter, Note, NoteVersion, Template, AuditLog, Patient, Draft, StatusEnum
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
    # Encounters reference templates via a nullable FK. Detach any encounters
    # still pointing at this template so the delete cannot raise an FK violation.
    db.query(Encounter).filter(Encounter.template_id == template_id)\
        .update({Encounter.template_id: None})
    db.add(AuditLog(
        actor_id=admin.id,
        action="delete_template",
        target_type="template",
        target_id=template_id,
    ))
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
        joinedload(Encounter.note).joinedload(Note.versions),
        joinedload(Encounter.draft),
    )
    if provider_id:
        q = q.filter(Encounter.provider_id == provider_id)
    if date_from:
        q = q.filter(Encounter.created_at >= date_from)
    if date_to:
        q = q.filter(Encounter.created_at <= date_to)
    encounters = q.order_by(Encounter.created_at.desc()).limit(200).all()

    result = []
    for e in encounters:
        is_invalid = False
        if e.note and e.note.versions:
            lc = e.note.versions[-1].content
            subj = lc.get("subjective", "") or ""
            asmt = lc.get("assessment", "") or ""
            plan = lc.get("plan", "") or ""
            is_invalid = (
                "Insufficient clinical content" in subj
                or "Unable to generate assessment" in asmt
                or "complete clinical transcript" in plan
            )
        else:
            _raw = (e.raw_input or "").strip()
            # A blank draft (no content yet) is not "invalid" — just empty
            is_invalid = bool(_raw) and not has_clinical_content(_raw)
        result.append({
            "encounter_id": e.id,
            "patient_id": e.patient_id,
            "patient_name": f"{e.patient.first_name} {e.patient.last_name}",
            "provider_name": f"{e.provider.first_name} {e.provider.last_name}",
            "status": e.status.value,
            "created_at": e.created_at.isoformat(),
            "updated_at": e.updated_at.isoformat(),
            "version_count": len(e.note.versions) if e.note else 0,
            "has_draft": e.draft is not None,
            "is_invalid": is_invalid,
        })
    return result


# --- Version view history (admin only) ---

@router.get("/version-views")
def list_version_views(
    encounter_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Return all view_version audit log entries.
    Providers cannot access this endpoint — admin only.
    Shows: who viewed each version, at what time.
    """
    from sqlalchemy import and_
    from models import NoteVersion

    q = (
        db.query(AuditLog)
        .options(joinedload(AuditLog.actor))
        .filter(AuditLog.action == "view_version")
        .order_by(AuditLog.created_at.desc())
        .limit(500)
    )
    if encounter_id:
        # Filter by encounter_id stored in extra JSON
        q = q.filter(AuditLog.target_id == encounter_id)

    logs = q.all()
    return [
        {
            "log_id": l.id,
            "viewer_name": f"{l.actor.first_name} {l.actor.last_name}" if l.actor else "Unknown",
            "viewer_email": l.actor.email if l.actor else None,
            "encounter_id": l.extra.get("encounter_id") if l.extra else l.target_id,
            "version_no": l.extra.get("version_no") if l.extra else None,
            "viewed_at": l.created_at.isoformat(),
        }
        for l in logs
    ]


@router.get("/encounters/{encounter_id}")
def get_encounter_admin(
    encounter_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    """Return full encounter detail for admin (bypasses provider-scoping)."""
    encounter = (
        db.query(Encounter)
        .options(
            joinedload(Encounter.patient),
            joinedload(Encounter.provider),
            joinedload(Encounter.note)
                .joinedload(Note.versions)
                .joinedload(NoteVersion.saver),
        )
        .filter(Encounter.id == encounter_id)
        .first()
    )
    if not encounter:
        raise HTTPException(status_code=404, detail="Encounter not found")

    versions = []
    if encounter.note and encounter.note.versions:
        versions = [
            {
                "version_no": v.version_no,
                "saved_at": v.saved_at.isoformat(),
                "saved_by_name": (
                    f"{v.saver.first_name} {v.saver.last_name}" if v.saver else "Unknown"
                ),
                "content": v.content,
            }
            for v in encounter.note.versions
        ]

    return {
        "encounter_id": encounter.id,
        "patient_name": f"{encounter.patient.first_name} {encounter.patient.last_name}",
        "provider_name": f"{encounter.provider.first_name} {encounter.provider.last_name}",
        "status": encounter.status.value,
        "created_at": encounter.created_at.isoformat(),
        "versions": versions,
    }


@router.get("/patients/{patient_id}/encounters")
def get_patient_encounters_admin(
    patient_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_admin),
):
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    encounters = (
        db.query(Encounter)
        .options(
            joinedload(Encounter.template),
            joinedload(Encounter.draft),
            joinedload(Encounter.note)
                .joinedload(Note.versions)
                .joinedload(NoteVersion.saver),
        )
        .filter(Encounter.patient_id == patient_id)
        .order_by(Encounter.created_at.desc())
        .all()
    )
    result = []
    for enc in encounters:
        submitted_at = None
        last_saved_at = None
        summary = None
        versions_list = []
        if enc.note and enc.note.versions:
            latest_ver = enc.note.versions[-1]
            last_saved_at = latest_ver.saved_at.isoformat()
            if enc.status == StatusEnum.saved:
                submitted_at = latest_ver.saved_at.isoformat()
            content = latest_ver.content
            icd_codes = content.get("icd10_codes", [])
            assessment = content.get("assessment", "")
            subjective = content.get("subjective", "")
            if icd_codes:
                reason = icd_codes[0]["description"]
            elif assessment:
                reason = assessment.split(".")[0][:120]
            elif subjective:
                reason = subjective.split(".")[0][:120]
            else:
                reason = "No diagnosis recorded"
            summary = {"reason": reason}

            lc = latest_ver.content
            subj = lc.get("subjective", "") or ""
            asmt = lc.get("assessment", "") or ""
            plan = lc.get("plan", "") or ""
            is_invalid = (
                "Insufficient clinical content" in subj
                or "Unable to generate assessment" in asmt
                or "complete clinical transcript" in plan
            )

            versions_list = [
                {
                    "version_no": v.version_no,
                    "saved_at": v.saved_at.isoformat(),
                    "saved_by_name": (
                        f"{v.saver.first_name} {v.saver.last_name}" if v.saver else "Unknown"
                    ),
                    "label": v.content.get("__label") if v.content else None,
                }
                for v in enc.note.versions
            ]
        result.append({
            "encounter_id": enc.id,
            "template_name": enc.template.name if enc.template else None,
            "status": enc.status.value,
            "created_at": enc.created_at.isoformat(),
            "updated_at": enc.updated_at.isoformat(),
            "submitted_at": submitted_at,
            "last_saved_at": last_saved_at,
            "version_count": len(enc.note.versions) if enc.note else 0,
            "versions": versions_list,
            "summary": summary,
            "has_draft": enc.draft is not None,
            "is_invalid": (is_invalid if enc.note and enc.note.versions else not has_clinical_content(enc.raw_input or "")),
        })
    return {
        "patient": {"id": patient.id, "first_name": patient.first_name, "last_name": patient.last_name, "dob": str(patient.dob)},
        "encounters": result,
    }
