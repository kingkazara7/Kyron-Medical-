from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from models import Draft, Encounter
from auth import get_current_provider
from models import Provider

router = APIRouter(prefix="/api/drafts", tags=["drafts"])


class DraftUpsert(BaseModel):
    encounter_id: int
    content: dict


@router.put("")
def upsert_draft(req: DraftUpsert, db: Session = Depends(get_db),
                 current: Provider = Depends(get_current_provider)):
    encounter = db.get(Encounter, req.encounter_id)
    if not encounter or encounter.provider_id != current.id:
        raise HTTPException(status_code=404, detail="Encounter not found")

    from sqlalchemy.orm.attributes import flag_modified
    draft = encounter.draft
    if draft:
        draft.content = req.content
        flag_modified(draft, 'content')  # ensure SQLAlchemy detects JSONB mutation
    else:
        draft = Draft(
            encounter_id=req.encounter_id,
            provider_id=current.id,
            content=req.content,
        )
        db.add(draft)
    db.commit()
    return {"status": "saved"}


@router.get("/{encounter_id}")
def get_draft(encounter_id: int, db: Session = Depends(get_db),
              current: Provider = Depends(get_current_provider)):
    encounter = db.get(Encounter, encounter_id)
    if not encounter or encounter.provider_id != current.id:
        raise HTTPException(status_code=404, detail="Encounter not found")
    if encounter.draft:
        return {"content": encounter.draft.content, "updated_at": encounter.draft.updated_at.isoformat()}
    return {"content": None}
