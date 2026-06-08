from database import SessionLocal
from sqlalchemy import text

db = SessionLocal()

sql = text("""
  SELECT e.id,
         p.first_name || ' ' || p.last_name AS patient_name,
         pr.first_name || ' ' || pr.last_name AS provider_name,
         COALESCE(t.name, 'No template') AS template_name,
         e.status,
         COUNT(DISTINCT nv.id) AS ver_count,
         COUNT(DISTINCT d.id) AS has_draft
  FROM encounters e
  JOIN patients p ON p.id = e.patient_id
  JOIN providers pr ON pr.id = e.provider_id
  LEFT JOIN templates t ON t.id = e.template_id
  LEFT JOIN notes n ON n.encounter_id = e.id
  LEFT JOIN note_versions nv ON nv.note_id = n.id
  LEFT JOIN drafts d ON d.encounter_id = e.id
  GROUP BY e.id, patient_name, provider_name, template_name, e.status
  ORDER BY e.id
""")

rows = db.execute(sql).fetchall()

print('=' * 88)
print('{:<3} | {:<22} | {:<18} | {:<22} | {:<10} | Vers | Draft'.format('ID','Patient','Provider','Template','Status'))
print('=' * 88)
for r in rows:
    draft_flag = 'YES' if r[6] else '-'
    print('{:<3} | {:<22} | {:<18} | {:<22} | {:<10} | {:>4} | {}'.format(
        r[0], r[1][:22], r[2][:18], r[3][:22], r[4], r[5], draft_flag))

# Version content snapshot
print()
print('--- Version content snapshot ---')
vcontent = text("""
  SELECT e.id,
         p.first_name || ' ' || p.last_name AS patient_name,
         nv.version_no,
         LEFT(nv.content->>'subjective', 70) AS subj
  FROM encounters e
  JOIN patients p ON p.id = e.patient_id
  JOIN notes n ON n.encounter_id = e.id
  JOIN note_versions nv ON nv.note_id = n.id
  ORDER BY e.id, nv.version_no
""")
rows2 = db.execute(vcontent).fetchall()

current_enc = None
for r in rows2:
    if r[0] != current_enc:
        current_enc = r[0]
        print('  Enc #{} - {}'.format(r[0], r[1]))
    subj = (r[3] or '')[:70]
    print('    v{}: {}...'.format(r[2], subj))

db.close()
print('\nDone.')
