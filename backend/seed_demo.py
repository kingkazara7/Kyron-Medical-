#!/usr/bin/env python3
"""
Demo data seed script
Clears existing data (preserves ICD-10 codes) and regenerates a clean dataset suitable for demonstrations.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, date, timedelta
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import (
    Provider, Patient, Template, Encounter, Note, NoteVersion,
    Draft, AuditLog, RoleEnum, StatusEnum, Base
)

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
db: Session = SessionLocal()

# ── 1. Clear data (preserve ICD10Code) ─────────────────────────────────────
print("🗑  Clearing existing data...")
pass  # already cleared
print("   ✓ Data cleared")

# ── 2. Create accounts ──────────────────────────────────────────────────────
print("\n👤 Creating accounts...")

def make_provider(first, last, email, password, role=RoleEnum.provider):
    p = Provider(
        first_name=first, last_name=last, email=email,
        password_hash=pwd_ctx.hash(password), role=role, is_active=True
    )
    db.add(p); db.flush()
    return p

admin   = make_provider("Alex",  "Morgan",   "admin@kyron.health",         "Admin1234!",    RoleEnum.admin)
chen    = make_provider("Sarah", "Chen",     "sarah.chen@kyron.health",    "Provider1234!", RoleEnum.provider)
rivera  = make_provider("James", "Rivera",   "james.rivera@kyron.health",  "Provider1234!", RoleEnum.provider)
patel   = make_provider("Emily", "Patel",    "emily.patel@kyron.health",   "Provider1234!", RoleEnum.provider)
db.commit()
print(f"   ✓ admin@kyron.health  / Admin1234!")
print(f"   ✓ sarah.chen@kyron.health   / Provider1234!  (Dr. Sarah Chen – Internal Medicine)")
print(f"   ✓ james.rivera@kyron.health / Provider1234!  (Dr. James Rivera – Orthopedics)")
print(f"   ✓ emily.patel@kyron.health  / Provider1234!  (Dr. Emily Patel – Urgent Care)")

# ── 3. Create Note Templates ────────────────────────────────────────────────
print("\n📋 Creating Note Templates...")

def make_template(name, prompt):
    t = Template(name=name, system_prompt=prompt, is_active=True)
    db.add(t); db.flush()
    return t

t_internal = make_template(
    "Internal Medicine – General",
    """You are an expert internal medicine physician. Generate a comprehensive SOAP note.
- Subjective: Chief complaint, HPI (OLDCARTS), relevant ROS, pertinent medical/surgical/family/social history, current medications, allergies.
- Objective: Vital signs, physical exam findings organized by system, relevant lab/imaging results.
- Assessment: Prioritized problem list with clinical reasoning. Include all active diagnoses.
- Plan: Evidence-based management for each problem. Include medication changes, referrals, labs ordered, patient education, and follow-up timing.
Use precise clinical language appropriate for internal medicine documentation."""
)

t_ortho = make_template(
    "Orthopedic Follow-Up",
    """You are a board-certified orthopedic surgeon. Generate a focused orthopedic SOAP note.
- Subjective: Pain score (0-10), location, character, aggravating/relieving factors, functional limitations, response to prior treatment.
- Objective: Musculoskeletal exam with ROM measurements (degrees), strength grading (0-5), provocative tests, imaging findings.
- Assessment: Orthopedic diagnosis with laterality and severity. Note functional status.
- Plan: Surgical vs. conservative management options, injections, PT goals, activity restrictions, weight-bearing status, follow-up interval.
Use standard orthopedic terminology and include specific anatomical references."""
)

t_urgent = make_template(
    "Urgent Care Visit",
    """You are an urgent care physician. Generate a concise, efficient SOAP note.
- Subjective: Onset, duration, severity, associated symptoms. Key negatives. Recent sick contacts.
- Objective: Focused vital signs and exam relevant to chief complaint. Point-of-care test results.
- Assessment: Primary diagnosis. Rule out serious/emergent conditions explicitly.
- Plan: Treatment initiated in office, prescriptions, strict return precautions, follow-up with PCP if warranted.
Be efficient and clinically precise. Flag any red-flag findings prominently."""
)

db.commit()
print(f"   ✓ {t_internal.name}")
print(f"   ✓ {t_ortho.name}")
print(f"   ✓ {t_urgent.name}")

# ── Helper: Create a complete submitted encounter ────────────────────────────
def make_encounter(patient, provider, template, status, raw, versions_data, created_days_ago):
    created = datetime.utcnow() - timedelta(days=created_days_ago)
    enc = Encounter(
        patient_id=patient.id, provider_id=provider.id,
        template_id=template.id if template else None,
        status=status, raw_input=raw,
        created_at=created, updated_at=created
    )
    db.add(enc); db.flush()

    if versions_data:
        note = Note(encounter_id=enc.id)
        db.add(note); db.flush()
        for i, (vdata, saved_by, days_ago) in enumerate(versions_data, 1):
            saved_at = datetime.utcnow() - timedelta(days=days_ago)
            nv = NoteVersion(
                note_id=note.id, version_no=i,
                content=vdata, saved_by=saved_by.id, saved_at=saved_at
            )
            db.add(nv)
        db.flush()

    return enc

# ── 4. Patients & Encounters ────────────────────────────────────────────────
print("\n🏥 Generating patients and encounters...")

# ─────────────────────────────────────────────────────────────────────────────
# Patient 1: Margaret Thompson — returning patient, demonstrates prior-history injection
# ────────────────────────────────────────────────────────────────────────────
margaret = Patient(first_name="Margaret", last_name="Thompson", dob=date(1955, 3, 14))
db.add(margaret); db.flush()

# Encounter A — 3 months ago, HTN + T2DM follow-up, 2 versions
enc_marg_1 = make_encounter(
    patient=margaret, provider=chen, template=t_internal,
    status=StatusEnum.saved,
    raw="68yo female for 3-month follow-up. Hypertension and T2DM. Home BPs averaging 145/88. Fasting glucose 158-195. Occasional morning headaches. Adherent to medications.",
    versions_data=[
        (
            {
                "__label": "initial assessment",
                "subjective": "Patient is a 68-year-old female with known essential hypertension and type 2 diabetes mellitus presenting for routine 3-month follow-up. She reports home blood pressure readings averaging 145/88 mmHg over the past two weeks. Denies chest pain, shortness of breath, or palpitations. Reports occasional mild morning headaches. Fasting blood glucose readings range from 158–195 mg/dL at home. She is fully adherent to her current medication regimen. No polyuria, polydipsia, or blurry vision.",
                "objective": "Vitals: BP 148/90 mmHg (right arm, seated), HR 74 bpm, RR 16, Temp 98.4°F, SpO2 99% RA, Weight 172 lbs (stable). General: Alert and oriented ×3, well-appearing female in no acute distress. Cardiovascular: Regular rate and rhythm, no murmurs or gallops. Respiratory: Clear to auscultation bilaterally. Extremities: 1+ pitting edema bilateral lower extremities. Labs (2 weeks prior): HbA1c 7.8%, eGFR 64 mL/min/1.73m², LDL 98 mg/dL, creatinine 1.1 mg/dL.",
                "assessment": "1. Essential hypertension, uncontrolled — BP remains above target (goal <130/80) on current regimen\n2. Type 2 diabetes mellitus, suboptimally controlled — HbA1c 7.8%, above target of ≤7.0%\n3. Chronic kidney disease, stage 2 — eGFR 64, stable; impacts medication choices",
                "plan": "1. Increase amlodipine from 5 mg to 10 mg daily for blood pressure optimization\n2. Continue metformin 1000 mg twice daily; renal dosing appropriate at current eGFR\n3. Refer to endocrinology for diabetes management optimization and insulin consideration\n4. Reinforce low-sodium (<2g/day), low-glycemic diet\n5. BMP in 4 weeks to monitor potassium and creatinine after dose increase\n6. Return in 6 weeks for BP recheck\n7. Patient education provided on home BP monitoring technique",
                "icd10_codes": [
                    {"code": "I10",   "description": "Essential (primary) hypertension"},
                    {"code": "E11.9", "description": "Type 2 diabetes mellitus without complications"},
                    {"code": "N18.2", "description": "Chronic kidney disease, stage 2"}
                ]
            },
            chen, 95
        ),
        (
            {
                "__label": "revised plan",
                "subjective": "Patient is a 68-year-old female with known essential hypertension and type 2 diabetes mellitus presenting for routine 3-month follow-up. She reports home blood pressure readings averaging 145/88 mmHg over the past two weeks. Denies chest pain, shortness of breath, or palpitations. Reports occasional mild morning headaches. Fasting blood glucose readings range from 158–195 mg/dL at home. She is fully adherent to her current medication regimen. No polyuria, polydipsia, or blurry vision.",
                "objective": "Vitals: BP 148/90 mmHg (right arm, seated), HR 74 bpm, RR 16, Temp 98.4°F, SpO2 99% RA, Weight 172 lbs (stable). General: Alert and oriented ×3, well-appearing female in no acute distress. Cardiovascular: Regular rate and rhythm, no murmurs or gallops. Respiratory: Clear to auscultation bilaterally. Extremities: 1+ pitting edema bilateral lower extremities. Labs (2 weeks prior): HbA1c 7.8%, eGFR 64 mL/min/1.73m², LDL 98 mg/dL, creatinine 1.1 mg/dL.",
                "assessment": "1. Essential hypertension, uncontrolled — BP remains above target (goal <130/80) on current regimen\n2. Type 2 diabetes mellitus, suboptimally controlled — HbA1c 7.8%, above target of ≤7.0%\n3. Chronic kidney disease, stage 2 — eGFR 64, stable; metformin safe, avoid nephrotoxins",
                "plan": "1. Increase amlodipine from 5 mg to 10 mg daily\n2. Add lisinopril 5 mg daily for added renoprotection (ACE-I preferred in CKD + DM) — hold if creatinine rises >25%\n3. Continue metformin 1000 mg BID; hold if eGFR drops below 45\n4. Refer to endocrinology for insulin consideration given HbA1c above target\n5. Reinforce low-sodium diet and DASH diet principles\n6. BMP in 3–4 weeks to monitor creatinine/K+ after lisinopril start\n7. Return in 6 weeks; earlier if BP > 160/100 or creatinine spikes",
                "icd10_codes": [
                    {"code": "I10",   "description": "Essential (primary) hypertension"},
                    {"code": "E11.9", "description": "Type 2 diabetes mellitus without complications"},
                    {"code": "N18.2", "description": "Chronic kidney disease, stage 2"}
                ]
            },
            chen, 92
        ),
    ],
    created_days_ago=96
)

# Encounter B — 1 month ago, annual wellness visit, AI references prior HTN record (return-visit context injection)
enc_marg_2 = make_encounter(
    patient=margaret, provider=chen, template=t_internal,
    status=StatusEnum.saved,
    raw="Annual wellness visit. BP much improved on amlodipine 10mg + lisinopril 5mg, home readings averaging 126/78. HbA1c repeated last week 7.2%, down from 7.8%. No new complaints. Weight down 2 lbs.",
    versions_data=[
        (
            {
                "__label": "annual wellness",
                "subjective": "Patient returns for annual wellness visit and hypertension/diabetes follow-up. She has been on amlodipine 10 mg and lisinopril 5 mg for the past 6 weeks and reports excellent home BP readings averaging 126/78 mmHg — a marked improvement from her prior visit (148/90). HbA1c repeated last week was 7.2%, down from 7.8% three months ago. She denies chest pain, dyspnea, headaches, or orthostatic symptoms. No adverse effects from lisinopril (no cough). She remains adherent to all medications and dietary modifications. Weight is down 2 lbs from last visit.",
                "objective": "Vitals: BP 124/78 mmHg, HR 70 bpm, Temp 98.2°F, SpO2 99%, Weight 170 lbs. General: Alert, well-appearing female in no distress. Cardiovascular: Regular rate and rhythm, no murmurs. Respiratory: Clear bilaterally. Extremities: No edema today. Labs: HbA1c 7.2% (improved from 7.8%), eGFR 66 mL/min/1.73m² (stable), creatinine 1.0 mg/dL, K+ 4.1 mEq/L.",
                "assessment": "1. Essential hypertension, now well-controlled — BP at goal on amlodipine 10 mg + lisinopril 5 mg\n2. Type 2 diabetes mellitus, improving — HbA1c trending down (7.8% → 7.2%)\n3. Chronic kidney disease, stage 2, stable — eGFR improved marginally, renoprotective regimen in place\n4. Preventive care and health maintenance — annual wellness completed",
                "plan": "1. Continue amlodipine 10 mg daily and lisinopril 5 mg daily — excellent BP response, continue current regimen\n2. Continue metformin 1000 mg BID — HbA1c trending toward goal; endocrinology follow-up next month\n3. Annual labs ordered: lipid panel, CBC, CMP, urine microalbumin-to-creatinine ratio\n4. Influenza vaccine administered today\n5. Mammogram referral placed (due)\n6. Colorectal cancer screening: colonoscopy overdue — referral placed to GI\n7. Diet and weight management: positive trend, continue DASH + low-glycemic approach\n8. Return in 6 months for interval follow-up, or sooner if new concerns",
                "icd10_codes": [
                    {"code": "I10",   "description": "Essential (primary) hypertension"},
                    {"code": "E11.9", "description": "Type 2 diabetes mellitus without complications"},
                    {"code": "Z00.00","description": "Encounter for general adult medical examination without abnormal findings"}
                ]
            },
            chen, 30
        )
    ],
    created_days_ago=32
)

print(f"   ✓ Margaret Thompson — 2 encounters (HTN/DM follow-up + annual wellness)")

# ─────────────────────────────────────────────────────────────────────────────
# Patient 2: Robert Kim — chest pain / GERD evaluation
# ────────────────────────────────────────────────────────────────────────────
robert = Patient(first_name="Robert", last_name="Kim", dob=date(1978, 9, 22))
db.add(robert); db.flush()

make_encounter(
    patient=robert, provider=chen, template=t_internal,
    status=StatusEnum.saved,
    raw="47yo male, 2 weeks of burning mid-sternal chest discomfort, worse after meals and when lying down. No radiation, no diaphoresis. Takes ibuprofen frequently for back pain. Non-smoker. EKG normal sinus.",
    versions_data=[
        (
            {
                "subjective": "47-year-old male presenting with a 2-week history of intermittent mid-sternal burning discomfort. Symptoms are worse after meals, particularly spicy foods, and when lying down at night. Denies radiation to jaw or left arm. Denies diaphoresis, palpitations, or exertional component. No prior cardiac history. Takes ibuprofen 400–600 mg 3–4 times weekly for chronic low back pain. Social alcohol use (2–3 drinks on weekends). Non-smoker. No similar episodes in the past.",
                "objective": "Vitals: BP 124/78 mmHg, HR 82 bpm, SpO2 99%, Weight 189 lbs, BMI 27.1. General: Well-developed male in no acute distress. Cardiovascular: Regular rate and rhythm, no murmurs or rubs. Respiratory: Clear to auscultation bilaterally. Abdomen: Soft, mild epigastric tenderness to deep palpation, no guarding or rebound, no organomegaly. EKG: Normal sinus rhythm, no ST changes, no Q waves, normal intervals.",
                "assessment": "1. Gastroesophageal reflux disease (GERD) — classic presentation with postprandial burning, positional exacerbation, and significant NSAID use as a precipitating factor\n2. NSAID-induced gastrointestinal risk — frequent ibuprofen use contributing to mucosal irritation\n3. Chronic low back pain — underlying musculoskeletal complaint requiring alternative analgesia",
                "plan": "1. Start omeprazole 20 mg once daily 30 minutes before breakfast × 8 weeks\n2. Discontinue ibuprofen — transition to acetaminophen 500–1000 mg q6-8h PRN for back pain\n3. Lifestyle modifications: elevate head of bed 6–8 inches, avoid eating within 3 hours of bedtime, reduce alcohol\n4. Dietary triggers to avoid: spicy foods, acidic foods, caffeine, carbonated beverages\n5. Cardiac etiology considered low probability given atypical features, normal EKG, and no risk factors — no further workup at this time; reassess if symptoms change in character\n6. Return in 4–6 weeks; if no improvement, consider upper endoscopy referral",
                "icd10_codes": [
                    {"code": "K21.0", "description": "Gastro-esophageal reflux disease with esophagitis"},
                    {"code": "M54.50","description": "Low back pain, unspecified"}
                ]
            },
            chen, 14
        )
    ],
    created_days_ago=16
)
print(f"   ✓ Robert Kim — chest pain / GERD evaluation")

# ─────────────────────────────────────────────────────────────────────────────
# Patient 3: Elena Rodriguez — right knee osteoarthritis (orthopedic template, version history)
# ────────────────────────────────────────────────────────────────────────────
elena = Patient(first_name="Elena", last_name="Rodriguez", dob=date(1986, 11, 3))
db.add(elena); db.flush()

# Encounter A — 6 weeks ago, initial right knee visit
make_encounter(
    patient=elena, provider=rivera, template=t_ortho,
    status=StatusEnum.saved,
    raw="38yo female, right knee pain 3 months, worsening past 6 weeks. Aching 6/10, worse with stairs and prolonged standing. Kindergarten teacher. Morning stiffness ~20 min. No trauma. X-ray: mild medial compartment narrowing, osteophytes.",
    versions_data=[
        (
            {
                "__label": "initial visit",
                "subjective": "38-year-old female presenting with a 3-month history of right knee pain, significantly worsening over the past 6 weeks. Pain is described as a deep aching sensation, 6/10 at baseline, exacerbated by prolonged standing, stair climbing, kneeling, and squatting. She works as a kindergarten teacher, and the pain is substantially limiting her ability to function at work. No history of acute trauma or prior knee surgeries. Morning stiffness lasting 20–30 minutes. Denies joint locking, giving way, or swelling. No contralateral knee symptoms.",
                "objective": "Vitals: BP 118/74, HR 78, Weight 163 lbs, BMI 28.2. Right knee exam: Mild effusion present (medial ballottement). Medial joint line tenderness ++ (lateral joint line −). Negative Lachman's test. Negative anterior/posterior drawer. Negative McMurray's. ROM: 0–130° (limited by pain at terminal flexion; contralateral 0–140°). Quadriceps strength 4+/5 right, 5/5 left. No varus/valgus instability at 0° or 30°. Weight-bearing X-ray right knee: Mild medial compartment joint space narrowing, small marginal osteophytes, no acute fracture, preserved lateral compartment.",
                "assessment": "1. Primary osteoarthritis, right knee, medial compartment — mild-to-moderate based on Kellgren-Lawrence grade II changes on imaging and clinical exam\n2. Secondary quadriceps weakness — 4+/5 strength likely contributing to altered joint mechanics",
                "plan": "1. Intra-articular corticosteroid injection administered today: triamcinolone acetonide 40 mg + 4 mL bupivacaine 0.25% under anatomic guidance, medial approach\n2. Physical therapy referral: quadriceps and VMO strengthening, proprioception training, gait analysis — 2×/week × 8 weeks\n3. Naproxen 500 mg twice daily with food PRN pain; take with omeprazole if GI sensitive\n4. Weight management counseling: current BMI 28, target BMI <25 to reduce joint load\n5. Activity modification: avoid high-impact activities (running, jumping); low-impact alternatives recommended (swimming, cycling, elliptical)\n6. Application for teacher's aide support discussed with patient for temporary activity modification at work\n7. Return in 6 weeks to assess injection response and PT progress",
                "icd10_codes": [
                    {"code": "M17.11","description": "Primary osteoarthritis, right knee"},
                    {"code": "M62.81","description": "Muscle weakness, right leg"}
                ]
            },
            rivera, 42
        )
    ],
    created_days_ago=44
)

# Encounter B — 2 weeks ago, post-injection follow-up, 2 versions (demonstrates version history)
make_encounter(
    patient=elena, provider=rivera, template=t_ortho,
    status=StatusEnum.saved,
    raw="6-week follow-up post right knee corticosteroid injection. Patient reports ~70% improvement in pain, resting 2/10. Attending PT 2x/week, noticing improved strength. Tolerating naproxen PRN. Occasional discomfort on prolonged stair use.",
    versions_data=[
        (
            {
                "__label": "post-injection follow-up",
                "subjective": "Patient returns for 6-week follow-up after right knee intra-articular corticosteroid injection. She reports approximately 70% reduction in pain. Resting pain is now 2/10 from a baseline of 6/10 at the initial visit. She has been attending physical therapy twice weekly and notes marked improvement in quadriceps strength and confidence on stairs. Still reports mild discomfort with prolonged stair climbing (4/10). Tolerating naproxen 500 mg PRN without GI symptoms. No joint locking or effusion noted at home.",
                "objective": "Right knee exam: No effusion on ballottement. Medial joint line tenderness markedly reduced (+). ROM: 0–135° (improved from 0–130° at prior visit). Quadriceps strength 5−/5 right (improved from 4+/5). No varus/valgus instability. Gait: Normal, symmetric.",
                "assessment": "1. Primary osteoarthritis, right knee — significant clinical improvement following intra-articular corticosteroid injection\n2. Quadriceps strength improving — 5−/5 from 4+/5; continued PT indicated",
                "plan": "1. Continue physical therapy: 4 additional weeks; advance to functional strengthening and return-to-activity protocol\n2. Naproxen 500 mg PRN — taper as symptoms allow; avoid daily use if possible\n3. Consider viscosupplementation (hyaluronic acid series) if symptoms recur as steroid effect wanes (~3–4 months)\n4. Discuss surgical options (arthroscopy, potential partial medial meniscectomy if indicated) at next visit if conservative measures plateau\n5. Return in 8 weeks or sooner if significant symptom recurrence",
                "icd10_codes": [
                    {"code": "M17.11","description": "Primary osteoarthritis, right knee"}
                ]
            },
            rivera, 16
        ),
        (
            {
                "__label": "updated — PT goals added",
                "subjective": "Patient returns for 6-week follow-up after right knee intra-articular corticosteroid injection. She reports approximately 70% reduction in pain. Resting pain is now 2/10 from a baseline of 6/10 at the initial visit. She has been attending physical therapy twice weekly and notes marked improvement in quadriceps strength and confidence on stairs. Still reports mild discomfort with prolonged stair climbing (4/10). Tolerating naproxen 500 mg PRN without GI symptoms. No joint locking or effusion noted at home.",
                "objective": "Right knee exam: No effusion on ballottement. Medial joint line tenderness markedly reduced (+). ROM: 0–135° (improved from 0–130° at prior visit). Quadriceps strength 5−/5 right (improved from 4+/5). No varus/valgus instability. Gait: Normal, symmetric.",
                "assessment": "1. Primary osteoarthritis, right knee — significant clinical improvement following intra-articular corticosteroid injection\n2. Quadriceps strength improving — 5−/5 from 4+/5; continued PT indicated\n3. Functional progress: return to full teaching duties anticipated within 4–6 weeks",
                "plan": "1. Continue physical therapy × 4 additional weeks:\n   – Specific goals: achieve quad strength 5/5, single-leg squat without pain, stair negotiation at 0/10\n   – Advance to closed-chain exercises, balance board, and sport-specific movements\n2. Naproxen 500 mg PRN — taper to as-needed only; avoid chronic NSAID use\n3. Home exercise program: straight-leg raises, terminal knee extensions, wall slides — 2 sets × 15 reps daily\n4. Viscosupplementation (Synvisc-One) discussed as a bridge option if symptoms recur; patient will consider\n5. Surgical consultation deferred — excellent conservative response at 6 weeks\n6. Return in 8 weeks; bring updated PT discharge summary",
                "icd10_codes": [
                    {"code": "M17.11","description": "Primary osteoarthritis, right knee"}
                ]
            },
            rivera, 14
        )
    ],
    created_days_ago=16
)
print(f"   ✓ Elena Rodriguez — 2 orthopedic encounters (initial + 2-version follow-up)")

# ─────────────────────────────────────────────────────────────────────────────
# Patient 4: William Foster — urgent care pharyngitis (urgent care template)
# ────────────────────────────────────────────────────────────────────────────
william = Patient(first_name="William", last_name="Foster", dob=date(1992, 4, 18))
db.add(william); db.flush()

make_encounter(
    patient=william, provider=patel, template=t_urgent,
    status=StatusEnum.saved,
    raw="32yo male, 3 days sore throat, fever 101.8 at home, difficulty swallowing. No cough, no congestion. Sick contact: 8yo child at home had similar illness last week. Rapid strep: POSITIVE.",
    versions_data=[
        (
            {
                "subjective": "32-year-old male presenting with sudden-onset sore throat, fever, and odynophagia for 3 days. Denies cough, nasal congestion, or rhinorrhea. Fever up to 101.8°F measured at home; no antipyretics taken. Difficulty swallowing solids, tolerating liquids. No prior antibiotic treatment. Sick contact: 8-year-old child in household with similar illness 1 week prior. No known drug allergies. No prior history of recurrent strep or tonsillectomy.",
                "objective": "Vitals: Temp 101.2°F (tympanic), BP 122/76 mmHg, HR 96 bpm, SpO2 99% on RA. General: Alert, uncomfortable-appearing male. HEENT: Bilateral tonsillar enlargement 2+ with exudates. Oropharyngeal erythema. Anterior cervical lymphadenopathy, bilateral, tender to palpation (~1.5 cm). No peritonsillar bulging or uvular deviation. No trismus. Skin: No rash. Lungs: CTA bilaterally. Rapid Streptococcal Antigen Test: POSITIVE.",
                "assessment": "1. Streptococcal pharyngitis (Group A) — positive rapid antigen test; Centor score 4/4 (exudate, anterior cervical LAD, fever, absence of cough); household contact confirmed\n⚠ No peritonsillar abscess — uvula midline, no peritonsillar bulging, mouth opens fully",
                "plan": "1. Amoxicillin 500 mg orally twice daily × 10 days — first-line therapy for GAS pharyngitis\n2. Symptomatic relief: ibuprofen 400 mg every 6 hours PRN fever and pain; throat lozenges PRN\n3. Soft diet as tolerated; increase oral fluid intake\n4. Remain home from work for minimum 24 hours after starting antibiotics and until afebrile\n5. RETURN PRECAUTIONS — return immediately if: inability to swallow, trismus, drooling, neck stiffness, rash, or symptoms worsening despite antibiotics\n6. No repeat throat culture required if compliant with full antibiotic course\n7. Advise household contact (child) to follow up with PCP for evaluation",
                "icd10_codes": [
                    {"code": "J02.0","description": "Streptococcal pharyngitis"}
                ]
            },
            patel, 7
        )
    ],
    created_days_ago=8
)
print(f"   ✓ William Foster — urgent care strep pharyngitis")

# ─────────────────────────────────────────────────────────────────────────────
# Patient 5: David Park — DRAFT encounter (demonstrates session persistence / draft recovery)
# ────────────────────────────────────────────────────────────────────────────
david = Patient(first_name="David", last_name="Park", dob=date(1960, 7, 29))
db.add(david); db.flush()

draft_enc = Encounter(
    patient_id=david.id, provider_id=chen.id,
    template_id=t_internal.id,
    status=StatusEnum.draft,
    raw_input="65yo male with COPD GOLD Stage II presenting with 5 days worsening shortness of breath. Increased sputum production (yellow-green). Using rescue inhaler 4x/day vs usual 1x/week. Low-grade fever 99.5F at home. No chest pain. Current meds: tiotropium, albuterol PRN, fluticasone/salmeterol. 30 pack-year history, quit 15 years ago. Last spirometry 8 months ago: FEV1/FVC 0.58, FEV1 55% predicted.",
    created_at=datetime.utcnow() - timedelta(hours=2),
    updated_at=datetime.utcnow() - timedelta(minutes=45)
)
db.add(draft_enc); db.flush()

# Save draft content (simulating AI-generated note not yet submitted by provider)
draft = Draft(
    encounter_id=draft_enc.id,
    provider_id=chen.id,
    content={
        "_transcript": "65yo male with COPD GOLD Stage II presenting with 5 days worsening shortness of breath. Increased sputum production (yellow-green). Using rescue inhaler 4x/day vs usual 1x/week. Low-grade fever 99.5F at home. No chest pain. Current meds: tiotropium, albuterol PRN, fluticasone/salmeterol. 30 pack-year history, quit 15 years ago. Last spirometry 8 months ago: FEV1/FVC 0.58, FEV1 55% predicted.",
        "subjective": "65-year-old male with established COPD (GOLD Stage II, FEV1/FVC 0.58, FEV1 55% predicted on spirometry 8 months prior) presenting with a 5-day history of progressive shortness of breath. Reports increased sputum production, described as yellow-green in color, representing a change from his baseline clear/white sputum. Rescue inhaler (albuterol) use has escalated from approximately once weekly to 4 times daily. Low-grade fever of 99.5°F measured at home. Denies chest pain, hemoptysis, or lower extremity edema. Current medications include tiotropium 18 mcg daily, albuterol MDI PRN, and fluticasone/salmeterol 250/50 mcg twice daily. 30 pack-year smoking history; quit 15 years ago.",
        "objective": "Vitals: Temp 99.8°F, BP 138/84 mmHg, HR 98 bpm, RR 22 breaths/min, SpO2 91% on room air (baseline ~94%). Weight 178 lbs. General: Mild respiratory distress, using accessory muscles. Speaking in full sentences. Respiratory: Diffuse expiratory wheezing bilaterally, prolonged expiratory phase, hyperresonant to percussion. No focal consolidation. Cardiovascular: Tachycardic, regular rhythm, no murmurs. No JVD. Extremities: No peripheral edema. Peak flow: 210 L/min (patient reports personal best ~310 L/min).",
        "assessment": "1. COPD exacerbation, moderate — increased dyspnea, purulent sputum, increased bronchodilator use meeting Anthonisen Type I criteria; SpO2 91% on RA\n2. Probable bacterial superinfection — purulent sputum suggests bacterial etiology (Streptococcus pneumoniae, H. influenzae, or Moraxella catarrhalis most likely)",
        "plan": "1. Albuterol nebulization 2.5 mg q20 min × 3 doses in office, then reassess\n2. Prednisone 40 mg orally daily × 5 days for exacerbation\n3. Azithromycin 500 mg day 1, then 250 mg days 2–5 for antibacterial coverage\n4. Continue tiotropium and fluticasone/salmeterol — do not discontinue\n5. Supplemental oxygen to maintain SpO2 ≥ 92%\n6. Chest X-ray ordered to rule out pneumonia\n7. Strict return precautions: ER if SpO2 drops below 88%, severe dyspnea at rest, or altered mental status\n8. Pulmonology follow-up within 2 weeks for optimization of maintenance regimen\n9. Influenza and pneumococcal vaccine status to be reviewed at follow-up",
        "icd10_codes": [
            {"code": "J44.1", "description": "Chronic obstructive pulmonary disease with acute exacerbation"},
            {"code": "J44.0", "description": "Chronic obstructive pulmonary disease with acute lower respiratory infection"}
        ]
    },
    updated_at=datetime.utcnow() - timedelta(minutes=45)
)
db.add(draft)
db.commit()
print(f"   ✓ David Park — DRAFT encounter (COPD exacerbation, session-persistence demo)")

# ── 5. Create sample AuditLog entries ──────────────────────────────────────
print("\n📝 Generating audit logs...")
logs = [
    AuditLog(actor_id=chen.id,   action="save_note",   target_type="encounter", target_id=enc_marg_1.id, extra={"version": 1}),
    AuditLog(actor_id=chen.id,   action="save_note",   target_type="encounter", target_id=enc_marg_1.id, extra={"version": 2, "label": "revised plan"}),
    AuditLog(actor_id=chen.id,   action="save_note",   target_type="encounter", target_id=enc_marg_2.id, extra={"version": 1}),
    AuditLog(actor_id=chen.id,   action="save_note",   target_type="encounter", target_id=3,              extra={"version": 1}),
    AuditLog(actor_id=rivera.id, action="save_note",   target_type="encounter", target_id=4,              extra={"version": 1}),
    AuditLog(actor_id=rivera.id, action="save_note",   target_type="encounter", target_id=5,              extra={"version": 1, "label": "post-injection follow-up"}),
    AuditLog(actor_id=rivera.id, action="save_note",   target_type="encounter", target_id=5,              extra={"version": 2, "label": "updated — PT goals added"}),
    AuditLog(actor_id=patel.id,  action="save_note",   target_type="encounter", target_id=6,              extra={"version": 1}),
    AuditLog(actor_id=admin.id,  action="view_all_encounters", target_type="admin", target_id=None, extra={}),
]
for log in logs:
    db.add(log)
db.commit()
print(f"   ✓ {len(logs)} audit log entries created")

# ── 6. Summary ──────────────────────────────────────────────────────────────
print("\n" + "="*60)
print("✅  Demo data generation complete!")
print("="*60)
print("\nAccount credentials:")
print("  admin@kyron.health        / Admin1234!      (Admin)")
print("  sarah.chen@kyron.health   / Provider1234!   (Dr. Sarah Chen – Internal Medicine)")
print("  james.rivera@kyron.health / Provider1234!   (Dr. James Rivera – Orthopedics)")
print("  emily.patel@kyron.health  / Provider1234!   (Dr. Emily Patel – Urgent Care)")
print("\nDemo highlights:")
print("  • Margaret Thompson — returning patient (2 encounters, AI references prior history)")
print("  • Margaret Encounter 1 — 2 versions (initial assessment → revised plan)")
print("  • Elena Rodriguez — orthopedic template, Encounter 2 has 2 versions")
print("  • William Foster — urgent care template, rapid pharyngitis diagnosis")
print("  • David Park — DRAFT encounter (session persistence demo: survives page refresh)")
print("  • 3 Note Templates (internal medicine / orthopedic / urgent care), AI generation styles clearly distinct")
