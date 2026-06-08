from database import SessionLocal
from models import NoteVersion, Note, Encounter
from sqlalchemy.orm import joinedload
from sqlalchemy import text

db = SessionLocal()

# Find all encounters for David Park
rows = db.execute(text("""
  SELECT e.id, p.first_name || ' ' || p.last_name AS patient, e.status,
         nv.version_no,
         LEFT(nv.content->>'subjective', 80) AS subj_preview,
         LEFT(nv.content->>'plan', 80) AS plan_preview,
         LEFT(nv.content->>'_transcript', 80) AS tx_preview,
         nv.saved_at
  FROM encounters e
  JOIN patients p ON p.id = e.patient_id
  JOIN notes n ON n.encounter_id = e.id
  JOIN note_versions nv ON nv.note_id = n.id
  WHERE p.first_name = 'David'
  ORDER BY e.id, nv.version_no
""")).fetchall()

print(f"Found {len(rows)} version rows for David Park")
print("=" * 70)

current_enc = None
for r in rows:
    if r[0] != current_enc:
        current_enc = r[0]
        print(f"\nEncounter #{r[0]} - {r[1]} ({r[2]})")
        print("-" * 50)
    print(f"  v{r[3]} saved at {r[7]}")
    print(f"    SUBJ: {r[4] or 'None'}...")
    print(f"    PLAN: {r[5] or 'None'}...")
    print(f"    TX:   {r[6] or 'None'}...")

db.close()
