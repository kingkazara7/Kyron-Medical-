from datetime import date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel
from database import get_db
from models import (
    Encounter, Patient, Note, NoteVersion, Template, AuditLog, Draft, StatusEnum
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


class GenerateRequest(BaseModel):
    encounter_id: int
    transcript: str
    template_id: Optional[int] = None


@router.post("")
def create_encounter(req: EncounterCreate, db: Session = Depends(get_db),
                     current: Provider = Depends(get_current_provider)):
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

    # Read template fresh from DB at generation time (not cached)
    template_id = req.template_id or encounter.template_id
    template = db.get(Template, template_id) if template_id else None

    # Save raw input
    encounter.raw_input = req.transcript
    db.commit()

    def event_stream():
        yield from stream_soap_note(
            transcript=req.transcript,
            patient_id=encounter.patient_id,
            encounter_id=encounter.id,
            template=template,
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
    version = NoteVersion(
        note_id=note.id,
        version_no=next_version,
        content=req.content.model_dump(),
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
        extra={"version": next_version},
    ))
    db.commit()

    return {"version_no": next_version, "encounter_id": encounter.id}


@router.get("/{encounter_id}")
def get_encounter(encounter_id: int, db: Session = Depends(get_db),
                  current: Provider = Depends(get_current_provider)):
    encounter = (
        db.query(Encounter)
        .options(
            joinedload(Encounter.patient),
            joinedload(Encounter.template),
            joinedload(Encounter.note).joinedload(Note.versions),
            joinedload(Encounter.draft),
        )
        .filter(Encounter.id == encounter_id)
        .first()
    )
    if not encounter or encounter.provider_id != current.id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    latest_version = None
    versions = []
    if encounter.note and encounter.note.versions:
        latest_version = encounter.note.versions[-1].content
        versions = [
            {
                "version_no": v.version_no,
                "saved_at": v.saved_at.isoformat(),
                "saved_by": v.saved_by,
                "content": v.content,
            }
            for v in encounter.note.versions
        ]

    draft_content = encounter.draft.content if encounter.draft else None

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


@router.get("")
def list_encounters(db: Session = Depends(get_db),
                    current: Provider = Depends(get_current_provider)):
    encounters = (
        db.query(Encounter)
        .options(joinedload(Encounter.patient), joinedload(Encounter.note))
        .filter(Encounter.provider_id == current.id)
        .order_by(Encounter.created_at.desc())
        .limit(50)
        .all()
    )

    return [
        {
            "encounter_id": e.id,
            "patient_name": f"{e.patient.first_name} {e.patient.last_name}",
            "status": e.status.value,
            "created_at": e.created_at.isoformat(),
            "has_note": e.note is not None,
            "version_count": len(e.note.versions) if e.note else 0,
        }
        for e in encounters
    ]
