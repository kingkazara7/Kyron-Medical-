from datetime import date
from typing import Optional, List
from services.ai import has_clinical_content
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from database import get_db
from models import (
    Encounter, Patient, Note, NoteVersion, Template, AuditLog, Draft, StatusEnum, RoleEnum
)
from auth import get_current_provider
from models import Provider
from services.ai import stream_soap_note

router = APIRouter(prefix="/api/encounters", tags=["encounters"])


class PatientIn(BaseModel):
    first_name: str
    last_name: str
    dob: date


class EncounterCreate(BaseModel):
    patient: PatientIn
    template_id: Optional[int] = None


class NoteContent(BaseModel):
    subjective: str
    objective: str
    assessment: str
    plan: str
    icd10_codes: List[dict]


class SaveNoteRequest(BaseModel):
    encounter_id: int
    content: NoteContent
    raw_input: Optional[str] = None
    label: Optional[str] = None   # version label, max 4 words, stored in content as __label


class GenerateRequest(BaseModel):
    encounter_id: int
    transcript: str
    template_id: Optional[int] = None


@router.post("")
def create_encounter(req: EncounterCreate, db: Session = Depends(get_db),
                     current: Provider = Depends(get_current_provider)):
    if current.role == RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Admins cannot create encounters")
    # Upsert patient by unique (first, last, dob)
    patient = db.query(Patient).filter(
        Patient.first_name == req.patient.first_name,
        Patient.last_name == req.patient.last_name,
        Patient.dob == req.patient.dob,
    ).first()
    if not patient:
        patient = Patient(
            first_name=req.patient.first_name,
            last_name=req.patient.last_name,
            dob=req.patient.dob,
        )
        db.add(patient)
        db.flush()

    encounter = Encounter(
        patient_id=patient.id,
        provider_id=current.id,
        template_id=req.template_id,
        status=StatusEnum.draft,
    )
    db.add(encounter)
    db.commit()
    db.refresh(encounter)

    return {
        "encounter_id": encounter.id,
        "patient_id": patient.id,
        "patient_name": f"{patient.first_name} {patient.last_name}",
        "is_returning": db.query(Encounter).filter(
            Encounter.patient_id == patient.id,
            Encounter.status == "saved"
        ).count() > 0,
    }


@router.post("/generate")
def generate_note(req: GenerateRequest, db: Session = Depends(get_db),
                  current: Provider = Depends(get_current_provider)):
    encounter = db.get(Encounter, req.encounter_id)
    if not encounter or encounter.provider_id != current.id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    template_id = req.template_id or encounter.template_id
    template = db.get(Template, template_id) if template_id else None

    patient_id = encounter.patient_id
    encounter_id = encounter.id
    from types import SimpleNamespace
    template_snapshot = (
        SimpleNamespace(name=template.name, system_prompt=template.system_prompt)
        if template else None
    )

    encounter.raw_input = req.transcript
    db.commit()

    def event_stream():
        yield from stream_soap_note(
            transcript=req.transcript,
            patient_id=patient_id,
            encounter_id=encounter_id,
            template=template_snapshot,
            db=db,
        )
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/save")
def save_note(req: SaveNoteRequest, db: Session = Depends(get_db),
              current: Provider = Depends(get_current_provider)):
    encounter = db.get(Encounter, req.encounter_id)
    if not encounter or encounter.provider_id != current.id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    if req.raw_input:
        encounter.raw_input = req.raw_input

    note = encounter.note
    if not note:
        note = Note(encounter_id=encounter.id)
        db.add(note)
        db.flush()

    next_version = len(note.versions) + 1

    # Build content dict; optionally embed the version label as __label
    content_dict = req.content.model_dump()
    # Snapshot the transcript so each version is fully self-contained
    if req.raw_input:
        content_dict['_transcript'] = req.raw_input
    if req.label:
        # Enforce 4-word max server-side as well
        words = req.label.strip().split()
        content_dict["__label"] = " ".join(words[:4])

    version = NoteVersion(
        note_id=note.id,
        version_no=next_version,
        content=content_dict,
        saved_by=current.id,
    )
    db.add(version)
    encounter.status = StatusEnum.saved

    # Remove draft on save
    if encounter.draft:
        db.delete(encounter.draft)

    db.add(AuditLog(
        actor_id=current.id,
        action="save_note",
        target_type="encounter",
        target_id=encounter.id,
        extra={"version": next_version, "label": content_dict.get("__label")},
    ))
    db.commit()

    return {"version_no": next_version, "encounter_id": encounter.id}


@router.get("")
def list_encounters(db: Session = Depends(get_db),
                    current: Provider = Depends(get_current_provider)):
    encounters = (
        db.query(Encounter)
        .options(
            joinedload(Encounter.patient),
            joinedload(Encounter.note).joinedload(Note.versions),
            joinedload(Encounter.draft),
        )
        .filter(Encounter.provider_id == current.id)
        .order_by(Encounter.created_at.desc())
        .limit(50)
        .all()
    )

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
            is_invalid = not has_clinical_content(e.raw_input or "")
        result.append({
            "encounter_id": e.id,
            "patient_id": e.patient_id,
            "patient_name": f"{e.patient.first_name} {e.patient.last_name}",
            "status": e.status.value,
            "created_at": e.created_at.isoformat(),
            "updated_at": e.updated_at.isoformat(),
            "has_note": e.note is not None,
            "version_count": len(e.note.versions) if e.note else 0,
            "has_draft": e.draft is not None,
            "is_invalid": is_invalid,
        })
    return result


# IMPORTANT: /patient/{patient_id} MUST be defined before /{encounter_id}.
@router.get("/patient/{patient_id}")
def get_patient_encounters(
    patient_id: int,
    db: Session = Depends(get_db),
    current: Provider = Depends(get_current_provider),
):
    """Return all encounters for a patient, scoped to the current provider."""
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
        .filter(
            Encounter.patient_id == patient_id,
            Encounter.provider_id == current.id,
        )
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

            # Check SOAP content for INSUFFICIENT_RESPONSE markers
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
                    # Surface label from content.__label (no schema change needed)
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
            # True if provider has unsaved draft edits in progress
            "has_draft": enc.draft is not None,
            "is_invalid": (is_invalid if enc.note and enc.note.versions else not has_clinical_content(enc.raw_input or "")),
        })

    return {
        "patient": {
            "id": patient.id,
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "dob": str(patient.dob),
        },
        "encounters": result,
    }


@router.post("/{encounter_id}/view-version/{version_no}")
def record_version_view(
    encounter_id: int,
    version_no: int,
    db: Session = Depends(get_db),
    current: Provider = Depends(get_current_provider),
):
    """Record that a provider viewed a specific version (admin-visible only)."""
    encounter = db.get(Encounter, encounter_id)
    if not encounter or encounter.provider_id != current.id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    db.add(AuditLog(
        actor_id=current.id,
        action="view_version",
        target_type="note_version",
        target_id=encounter_id,
        extra={"encounter_id": encounter_id, "version_no": version_no},
    ))
    db.commit()
    return {"recorded": True}


@router.delete("/{encounter_id}")
def delete_encounter(
    encounter_id: int,
    db: Session = Depends(get_db),
    current: Provider = Depends(get_current_provider),
):
    """Delete a draft encounter (draft status only — submitted notes cannot be deleted)."""
    encounter = (
        db.query(Encounter)
        .options(
            joinedload(Encounter.draft),
            joinedload(Encounter.note).joinedload(Note.versions),
        )
        .filter(Encounter.id == encounter_id)
        .first()
    )
    if not encounter or encounter.provider_id != current.id:
        raise HTTPException(status_code=404, detail="Encounter not found")
    if encounter.status != StatusEnum.draft:
        raise HTTPException(status_code=400, detail="Only draft encounters can be deleted")

    # Explicitly delete related records before the encounter itself
    if encounter.draft:
        db.delete(encounter.draft)
    if encounter.note:
        for v in encounter.note.versions:
            db.delete(v)
        db.delete(encounter.note)

    db.delete(encounter)
    db.commit()
    return {"deleted": True, "encounter_id": encounter_id}


class EncounterTemplateUpdate(BaseModel):
    template_id: Optional[int] = None


@router.patch("/{encounter_id}/template")
def update_encounter_template(
    encounter_id: int,
    req: EncounterTemplateUpdate,
    db: Session = Depends(get_db),
    current: Provider = Depends(get_current_provider),
):
    """Update the note template for an encounter (takes effect on next Generate)."""
    encounter = db.get(Encounter, encounter_id)
    if not encounter or encounter.provider_id != current.id:
        raise HTTPException(status_code=404, detail="Encounter not found")
    encounter.template_id = req.template_id
    db.commit()
    template_name = None
    if req.template_id:
        tmpl = db.get(Template, req.template_id)
        template_name = tmpl.name if tmpl else None
    return {"template_id": req.template_id, "template_name": template_name}


@router.get("/{encounter_id}")
def get_encounter(encounter_id: int, db: Session = Depends(get_db),
                  current: Provider = Depends(get_current_provider)):
    encounter = (
        db.query(Encounter)
        .options(
            joinedload(Encounter.patient),
            joinedload(Encounter.template),
            joinedload(Encounter.note).joinedload(Note.versions).joinedload(NoteVersion.saver),
            joinedload(Encounter.draft),
        )
        .filter(Encounter.id == encounter_id)
        .first()
    )
    if not encounter or (encounter.provider_id != current.id and current.role != RoleEnum.admin):
        raise HTTPException(status_code=404, detail="Encounter not found")
    # Admin gets read-only view: never expose draft
    is_admin_view = current.role == RoleEnum.admin

    latest_version = None
    versions = []
    if encounter.note and encounter.note.versions:
        latest_version = encounter.note.versions[-1].content
        versions = [
            {
                "version_no": v.version_no,
                "saved_at": v.saved_at.isoformat(),
                "saved_by": v.saved_by,
                "saved_by_name": f"{v.saver.first_name} {v.saver.last_name}" if v.saver else "Unknown",
                "content": v.content,  # includes __label if present
            }
            for v in encounter.note.versions
        ]

    draft_content = (encounter.draft.content if encounter.draft else None) if not is_admin_view else None

    return {
        "encounter_id": encounter.id,
        "patient": {
            "id": encounter.patient.id,
            "first_name": encounter.patient.first_name,
            "last_name": encounter.patient.last_name,
            "dob": str(encounter.patient.dob),
        },
        "template_id": encounter.template_id,
        "template_name": encounter.template.name if encounter.template else None,
        "status": encounter.status.value,
        "raw_input": encounter.raw_input,
        "latest_version": latest_version,
        "versions": versions,
        "draft": draft_content,
        "created_at": encounter.created_at.isoformat(),
    }
