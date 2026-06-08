"""
Backfill _transcript into existing NoteVersion.content records.
Uses ORM to avoid jsonb cast syntax issues.
"""
import json
from database import SessionLocal
from models import NoteVersion, Note, Encounter
from sqlalchemy.orm import joinedload

db = SessionLocal()

# enc 15 Margaret Thompson - v1 and v2
enc15_base = (
    "68F established patient presenting for quarterly hypertension and diabetes management. "
    "Current BP readings at home averaging 148/88 mmHg. Reports occasional headaches, "
    "no visual changes. Metformin 1000mg BID ongoing, no GI side effects. Last A1c 7.8% "
    "from 3 months ago. eGFR 62 (CKD stage 2). Denies chest pain, SOB. Compliant with "
    "low-sodium diet but struggles with carbohydrate restriction. Requests refill for "
    "amlodipine 5mg. No new allergies."
)
enc15_v1_tx = enc15_base + "\n\n[Physician note] Plan: increase amlodipine to 10mg, refer endocrinology."
enc15_v2_tx = enc15_base + "\n\n[Physician note — REVISED] After CKD review: add lisinopril 5mg for ACE-inhibitor renoprotection. Revised plan finalized."

enc16_tx = (
    "68F annual wellness visit. Reports feeling generally well. "
    "Weight stable. BP and diabetes management per prior plan. No new complaints. "
    "BMI 27.2. Mammogram due. Colonoscopy up to date. Flu vaccine at pharmacy. "
    "Depression screen negative (PHQ-9 = 2). Bone density scan recommended."
)

enc17_tx = (
    "47M presenting with 2-week history of intermittent mid-epigastric burning pain, "
    "worse after meals and when lying down. Rates 5/10. Occasional regurgitation, no dysphagia. "
    "No hematemesis, melena. Takes ibuprofen 400mg PRN ~3x/week for back pain. "
    "Current meds: lisinopril 10mg, atorvastatin 40mg. No prior GI workup. "
    "2 cups coffee/day, no alcohol. Non-smoker. Father had peptic ulcer disease."
)

enc18_tx = (
    "38F presenting with 3-month history of right knee pain. Worsens with stairs, "
    "prolonged standing, after exercise. Rates 6/10 worst. Mild intermittent swelling after activity. "
    "No locking or giving way. No prior knee injuries or surgeries. Nurse—on feet 10h/day. "
    "Ibuprofen 400mg PRN partial relief. X-ray 6 weeks ago: mild joint space narrowing medial compartment. "
    "BMI 29. Active: walks 3 miles/day."
)

enc19_base_tx = (
    "38F follow-up 6 weeks after right knee intra-articular corticosteroid injection. "
    "Pain improved from 6/10 to 2-3/10 with activity. Swelling markedly reduced. "
    "Still has discomfort on stairs and prolonged standing. Physical therapy 2x/week—helping. "
    "Naproxen use reduced to PRN only. Returned to modified work duties."
)
enc19_v2_tx = enc19_base_tx + "\n\n[Physician note — REVISED] Patient requested specific PT goals. Added measurable targets: quad strength 5/5, single-leg squat, stair negotiation. Timeline 4 more weeks, then reassess for PRP or surgical consult."

enc20_tx = (
    "32M presenting with sudden-onset sore throat, fever 101.8F, difficulty swallowing. "
    "Onset 2 days ago. No cough, no runny nose. Tonsillar exudates on exam. "
    "Tender anterior cervical lymphadenopathy. No known sick contacts. Office worker. "
    "No penicillin allergy. No current medications. Requests rapid strep test."
)

# Map: (encounter_id, version_no) -> transcript
tx_map = {
    (15, 1): enc15_v1_tx,
    (15, 2): enc15_v2_tx,
    (16, 1): enc16_tx,
    (17, 1): enc17_tx,
    (18, 1): enc18_tx,
    (19, 1): enc19_base_tx,
    (19, 2): enc19_v2_tx,
    (20, 1): enc20_tx,
}

for (enc_id, ver_no), transcript in tx_map.items():
    nv = (
        db.query(NoteVersion)
        .join(NoteVersion.note)
        .filter(Note.encounter_id == enc_id, NoteVersion.version_no == ver_no)
        .first()
    )
    if nv is None:
        print(f'WARN: enc #{enc_id} v{ver_no} not found, skipping')
        continue

    # Merge _transcript into existing content (copy dict to trigger JSONB update)
    updated_content = dict(nv.content)
    updated_content['_transcript'] = transcript

    # SQLAlchemy detects dict identity change via flag_modified
    from sqlalchemy.orm.attributes import flag_modified
    nv.content = updated_content
    flag_modified(nv, 'content')

    print(f'Enc #{enc_id} v{ver_no}: transcript backfilled ({len(transcript)} chars)')

db.commit()
db.close()
print('\nBackfill complete.')
