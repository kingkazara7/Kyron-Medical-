from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

# Check plan content for encounters with multiple versions
vcontent = text("""
  SELECT e.id,
         p.first_name || ' ' || p.last_name AS patient_name,
         nv.version_no,
         LEFT(nv.content->>'plan', 200) AS plan,
         LEFT(nv.content->>'assessment', 120) AS assessment
  FROM encounters e
  JOIN patients p ON p.id = e.patient_id
  JOIN notes n ON n.encounter_id = e.id
  JOIN note_versions nv ON nv.note_id = n.id
  WHERE e.id IN (15, 19)
  ORDER BY e.id, nv.version_no
""")
rows = db.execute(vcontent).fetchall()

current_enc = None
for r in rows:
    if r[0] != current_enc:
        current_enc = r[0]
        print('Enc #{} - {}'.format(r[0], r[1]))
        print('=' * 60)
    print('  v{} PLAN: {}...'.format(r[2], r[3] or 'None'))
    print('  v{} ASSESS: {}...'.format(r[2], r[4] or 'None'))
    print()

db.close()
