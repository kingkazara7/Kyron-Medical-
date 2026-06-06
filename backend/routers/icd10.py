from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from database import get_db
from auth import get_current_provider
from services.ai import search_icd10_semantic

router = APIRouter(prefix="/api/icd10", tags=["icd10"])


@router.get("/search")
def search_icd10(
    q: str = Query(..., min_length=2),
    limit: int = Query(8, ge=1, le=20),
    db: Session = Depends(get_db),
    _=Depends(get_current_provider),
):
    results = search_icd10_semantic(query=q, db=db, top_k=limit)
    return {"results": results, "query": q}
