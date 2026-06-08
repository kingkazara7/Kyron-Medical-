"""
Reset David Park encounter #21:
- Delete the 3 identical user-created versions
- Create 2 clean demo versions with meaningfully different content
  v1: Initial COPD exacerbation assessment
  v2: Revised plan after CXR results + added azithromycin
"""
from database import SessionLocal
from models import Encounter, Note, NoteVersion, Draft, Provider, StatusEnum
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta

db = SessionLocal()

enc = db.query(Encounter).options(
    joinedload(Encounter.note).joinedload(Note.versions),
    joinedload(Encounter.draft)
).filter(Encounter.id == 21).first()

if not enc:
    print("Encounter 21 not found!")
    db.close()
    exit(1)

# Delete existing versions
if enc.note:
    print(f"Deleting {len(enc.note.versions)} existing versions...")
    for v in list(enc.note.versions):
        db.delete(v)
    db.flush()
    note = enc.note
else:
    note = Note(encounter_id=21)
    db.add(note)
    db.flush()

# Delete any draft
if enc.draft:
    db.delete(enc.draft)
    db.flush()

# Get Sarah Chen's provider ID
chen = db.query(Provider).filter(Provider.email == 'sarah.chen@kyron.health').first()

now = datetime.utcnow()

# ── v1: Initial assessment ───────────────────────────────────────────────────
transcript_v1 = (
    "65yo male with COPD GOLD Stage II presenting with 5 days worsening shortness of breath. "
    "Increased sputum production (yellow-green). Using rescue inhaler 4x/day vs usual 1x/week. "
    "Low-grade fever 99.5F at home. No chest pain. Current meds: tiotropium, albuterol PRN, "
    "fluticasone/salmeterol. 30 pack-year history, quit 15 years ago. "
    "Last spirometry 8 months ago: FEV1/FVC 0.58, FEV1 55% predicted."
)

v1 = NoteVersion(
    note_id=note.id,
    version_no=1,
    content={
        "__label": "initial assessment",
        "_transcript": transcript_v1,
        "subjective": (
            "65-year-old male with established COPD (GOLD Stage II, FEV1/FVC 0.58, FEV1 55% predicted "
            "on spirometry 8 months prior) presenting with a 5-day history of progressive shortness of breath. "
            "Reports increased sputum production, yellow-green in color. Rescue inhaler use escalated from "
            "once weekly to 4 times daily. Low-grade fever 99.5°F at home. Denies chest pain, hemoptysis, "
            "or lower extremity edema. Current medications: tiotropium 18 mcg daily, albuterol MDI PRN, "
            "fluticasone/salmeterol 250/50 mcg BID. 30 pack-year smoking history; quit 15 years ago."
        ),
        "objective": (
            "Vitals: Temp 99.8°F, BP 138/84 mmHg, HR 98 bpm, RR 22 breaths/min, SpO2 91% on room air "
            "(baseline ~94%). Weight 178 lbs. General: Mild respiratory distress, accessory muscle use. "
            "Respiratory: Diffuse expiratory wheezing bilaterally, prolonged expiratory phase, no focal "
            "consolidation. Cardiovascular: Tachycardic, regular rhythm. Extremities: No edema."
        ),
        "assessment": (
            "1. COPD exacerbation, moderate (Anthonisen Type I: increased dyspnea, sputum volume, "
            "sputum purulence); SpO2 91% on RA\n"
            "2. Probable bacterial superinfection — purulent sputum suggests bacterial etiology\n"
            "3. Chest X-ray ordered to rule out pneumonia — results pending"
        ),
        "plan": (
            "1. Albuterol nebulization 2.5 mg q20 min × 3 doses in office, then reassess\n"
            "2. Prednisone 40 mg PO daily × 5 days\n"
            "3. Chest X-ray ordered STAT — await results before finalizing antibiotic plan\n"
            "4. Continue tiotropium and fluticasone/salmeterol\n"
            "5. Supplemental O2 to maintain SpO2 ≥ 92%\n"
            "6. Strict return precautions: ER if SpO2 < 88% or worsening distress"
        ),
        "icd10_codes": [
            {"code": "J44.1", "description": "COPD with acute exacerbation"},
            {"code": "J44.0", "description": "COPD with acute lower respiratory infection"}
        ]
    },
    saved_by=chen.id,
    saved_at=now - timedelta(hours=2),
)
db.add(v1)

# ── v2: Revised after CXR results ────────────────────────────────────────────
transcript_v2 = (
    "65yo male with COPD GOLD Stage II presenting with 5 days worsening shortness of breath. "
    "Increased sputum production (yellow-green). Using rescue inhaler 4x/day vs usual 1x/week. "
    "Low-grade fever 99.5F at home. No chest pain. Current meds: tiotropium, albuterol PRN, "
    "fluticasone/salmeterol. 30 pack-year history, quit 15 years ago. "
    "Last spirometry 8 months ago: FEV1/FVC 0.58, FEV1 55% predicted.\n\n"
    "[ADDENDUM] CXR results reviewed: No focal consolidation or infiltrate. "
    "Bilateral hyperinflation consistent with COPD. No pneumothorax. "
    "Decided to add azithromycin for antibacterial coverage given purulent sputum "
    "despite clear CXR. Patient tolerated 3 albuterol nebs well — SpO2 improved to 94% on 2L NC."
)

v2 = NoteVersion(
    note_id=note.id,
    version_no=2,
    content={
        "__label": "revised CXR reviewed",
        "_transcript": transcript_v2,
        "subjective": (
            "65-year-old male with established COPD (GOLD Stage II) presenting with 5-day history of "
            "progressive dyspnea, purulent yellow-green sputum, and increased albuterol use (4×/day from "
            "baseline once weekly). Fever 99.5°F at home. No chest pain or hemoptysis. "
            "CXR reviewed: bilateral hyperinflation consistent with COPD, no focal consolidation or "
            "infiltrate, no pneumothorax. Post-nebulization SpO2 improved from 91% to 94% on 2L NC. "
            "Patient tolerated 3 albuterol nebulizations without adverse effect."
        ),
        "objective": (
            "Vitals: Temp 99.8°F, BP 138/84 mmHg, HR 98 bpm, RR 22 breaths/min, SpO2 91% on RA → "
            "94% on 2L NC after nebulizations. Weight 178 lbs.\n"
            "Respiratory: Diffuse expiratory wheezing bilaterally, prolonged expiratory phase. "
            "Improved air movement post-nebulization. No focal consolidation.\n"
            "CXR: Bilateral hyperinflation, flat diaphragms. No pneumonia, no pneumothorax, no effusion."
        ),
        "assessment": (
            "1. COPD exacerbation, moderate (Anthonisen Type I); SpO2 improved to 94% post-treatment\n"
            "2. Bacterial superinfection likely (purulent sputum) — CXR clears pneumonia\n"
            "3. Plan updated: initiate azithromycin for antibacterial coverage"
        ),
        "plan": (
            "1. Albuterol nebulization completed × 3 doses — good response (SpO2 91% → 94%)\n"
            "2. Prednisone 40 mg PO daily × 5 days — initiated\n"
            "3. Azithromycin 500 mg PO day 1, then 250 mg PO days 2–5 — ADDED after CXR review\n"
            "   (CXR negative for pneumonia; azithromycin chosen for atypical coverage + anti-inflammatory)\n"
            "4. Continue tiotropium 18 mcg daily + fluticasone/salmeterol 250/50 mcg BID\n"
            "5. Supplemental O2: 2L NC, titrate to SpO2 ≥ 92%\n"
            "6. Pulmonology follow-up within 2 weeks\n"
            "7. Return precautions: ER if SpO2 < 88%, worsening distress, or fever > 101.5°F"
        ),
        "icd10_codes": [
            {"code": "J44.1", "description": "COPD with acute exacerbation"},
            {"code": "J44.0", "description": "COPD with acute lower respiratory infection"},
            {"code": "J06.9", "description": "Acute upper respiratory infection, unspecified"}
        ]
    },
    saved_by=chen.id,
    saved_at=now - timedelta(minutes=30),
)
db.add(v2)

# Update encounter raw_input to v2 transcript (latest)
enc.raw_input = transcript_v2
enc.status = StatusEnum.saved

db.commit()
print("Done. Encounter #21 (David Park) reset with 2 clean versions:")
print("  v1: 'initial assessment' — pending CXR, no azithromycin yet")
print("  v2: 'revised CXR reviewed' — CXR clear, azithromycin added, SpO2 improved")
db.close()
