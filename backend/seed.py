"""Seed script: providers, templates, and 250+ ICD-10 codes with embeddings."""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from database import engine, SessionLocal, Base
import models
from auth import hash_password
from services.icd10_embeddings import embed_description

ICD10_CODES = [
    ("I10", "Essential (primary) hypertension"),
    ("E11.9", "Type 2 diabetes mellitus without complications"),
    ("E11.65", "Type 2 diabetes mellitus with hyperglycemia"),
    ("E11.40", "Type 2 diabetes mellitus with diabetic neuropathy, unspecified"),
    ("E11.311", "Type 2 diabetes mellitus with unspecified diabetic retinopathy with macular edema"),
    ("E10.9", "Type 1 diabetes mellitus without complications"),
    ("J06.9", "Acute upper respiratory infection, unspecified"),
    ("J20.9", "Acute bronchitis, unspecified"),
    ("J44.1", "Chronic obstructive pulmonary disease with acute exacerbation"),
    ("J45.901", "Unspecified asthma with acute exacerbation"),
    ("J45.20", "Mild intermittent asthma, uncomplicated"),
    ("J18.9", "Pneumonia, unspecified organism"),
    ("J11.1", "Influenza due to unidentified influenza virus with other respiratory manifestations"),
    ("R05.9", "Cough, unspecified"),
    ("R06.00", "Dyspnea, unspecified"),
    ("R51.9", "Headache, unspecified"),
    ("G43.909", "Migraine, unspecified, not intractable, without status migrainosus"),
    ("R42", "Dizziness and giddiness"),
    ("H81.10", "Benign paroxysmal vertigo, unspecified ear"),
    ("R10.9", "Unspecified abdominal pain"),
    ("R10.0", "Acute abdomen"),
    ("K21.0", "Gastro-esophageal reflux disease with esophagitis"),
    ("K25.9", "Gastric ulcer, unspecified as acute or chronic, without hemorrhage or perforation"),
    ("K58.9", "Irritable bowel syndrome without diarrhea"),
    ("K57.30", "Diverticulosis of large intestine without perforation or abscess without bleeding"),
    ("K29.70", "Gastritis, unspecified, without bleeding"),
    ("K92.1", "Melena"),
    ("R11.2", "Nausea with vomiting, unspecified"),
    ("M54.5", "Low back pain"),
    ("M54.2", "Cervicalgia"),
    ("M54.16", "Radiculopathy, lumbar region"),
    ("M54.12", "Radiculopathy, cervical region"),
    ("M17.11", "Primary osteoarthritis, right knee"),
    ("M17.12", "Primary osteoarthritis, left knee"),
    ("M16.11", "Primary osteoarthritis, right hip"),
    ("M16.12", "Primary osteoarthritis, left hip"),
    ("M19.011", "Primary osteoarthritis, right shoulder"),
    ("M06.9", "Rheumatoid arthritis, unspecified"),
    ("M10.9", "Gout, unspecified"),
    ("M81.0", "Age-related osteoporosis without current pathological fracture"),
    ("M79.3", "Panniculitis, unspecified"),
    ("M79.1", "Myalgia"),
    ("M62.838", "Muscle weakness, other site"),
    ("F32.9", "Major depressive disorder, single episode, unspecified"),
    ("F33.9", "Major depressive disorder, recurrent, unspecified"),
    ("F41.1", "Generalized anxiety disorder"),
    ("F41.0", "Panic disorder without agoraphobia"),
    ("F43.10", "Post-traumatic stress disorder, unspecified"),
    ("F51.01", "Primary insomnia"),
    ("F32.1", "Major depressive disorder, single episode, moderate"),
    ("F90.9", "Attention-deficit hyperactivity disorder, unspecified type"),
    ("F84.0", "Autistic disorder"),
    ("F31.9", "Bipolar disorder, unspecified"),
    ("F20.9", "Schizophrenia, unspecified"),
    ("F42.9", "Obsessive-compulsive disorder, unspecified"),
    ("F10.20", "Alcohol use disorder, moderate, uncomplicated"),
    ("F11.20", "Opioid dependence, uncomplicated"),
    ("Z87.891", "Personal history of nicotine dependence"),
    ("I25.10", "Atherosclerotic heart disease of native coronary artery without angina pectoris"),
    ("I21.9", "Acute myocardial infarction, unspecified"),
    ("I48.0", "Paroxysmal atrial fibrillation"),
    ("I48.91", "Unspecified atrial fibrillation"),
    ("I50.9", "Heart failure, unspecified"),
    ("I50.32", "Chronic diastolic (congestive) heart failure"),
    ("I27.0", "Primary pulmonary hypertension"),
    ("I63.9", "Cerebral infarction, unspecified"),
    ("G45.9", "Transient cerebral ischemic attack, unspecified"),
    ("I73.9", "Peripheral vascular disease, unspecified"),
    ("I82.401", "Acute deep vein thrombosis of unspecified tibial vein"),
    ("I26.99", "Other pulmonary embolism without acute cor pulmonale"),
    ("N18.3", "Chronic kidney disease, stage 3 (moderate)"),
    ("N18.4", "Chronic kidney disease, stage 4 (severe)"),
    ("N18.6", "End-stage renal disease"),
    ("N39.0", "Urinary tract infection, site not specified"),
    ("N20.0", "Calculus of kidney"),
    ("N40.1", "Benign prostatic hyperplasia with lower urinary tract symptoms"),
    ("N93.9", "Abnormal uterine and vaginal bleeding, unspecified"),
    ("N94.6", "Dysmenorrhea, unspecified"),
    ("N83.20", "Unspecified ovarian cysts"),
    ("N80.0", "Endometriosis of uterus"),
    ("L03.011", "Cellulitis of right toe"),
    ("L03.115", "Cellulitis of right lower limb"),
    ("L30.9", "Dermatitis, unspecified"),
    ("L20.9", "Atopic dermatitis, unspecified"),
    ("L40.0", "Psoriasis vulgaris"),
    ("L50.9", "Urticaria, unspecified"),
    ("C34.10", "Malignant neoplasm of upper lobe, bronchus or lung, unspecified side"),
    ("C50.911", "Malignant neoplasm of unspecified site of right female breast"),
    ("C18.9", "Malignant neoplasm of colon, unspecified"),
    ("C61", "Malignant neoplasm of prostate"),
    ("C44.91", "Unspecified malignant neoplasm of skin, unspecified"),
    ("C43.9", "Malignant melanoma of skin, unspecified"),
    ("C91.00", "Acute lymphoblastic leukemia not having achieved remission"),
    ("C85.90", "Non-Hodgkin lymphoma, unspecified, unspecified site"),
    ("E03.9", "Hypothyroidism, unspecified"),
    ("E05.90", "Thyrotoxicosis, unspecified, without thyrotoxic crisis or storm"),
    ("E66.9", "Obesity, unspecified"),
    ("E66.01", "Morbid (severe) obesity due to excess calories"),
    ("E78.5", "Hyperlipidemia, unspecified"),
    ("E78.00", "Pure hypercholesterolemia, unspecified"),
    ("E55.9", "Vitamin D deficiency, unspecified"),
    ("E53.8", "Deficiency of other specified B group vitamins"),
    ("D50.9", "Iron deficiency anemia, unspecified"),
    ("D64.9", "Anemia, unspecified"),
    ("G40.909", "Epilepsy, unspecified, not intractable, without status epilepticus"),
    ("G20", "Parkinson disease"),
    ("G30.9", "Alzheimer disease, unspecified"),
    ("F03.90", "Unspecified dementia without behavioral disturbance"),
    ("G35", "Multiple sclerosis"),
    ("G62.9", "Polyneuropathy, unspecified"),
    ("G89.29", "Other chronic pain"),
    ("G89.4", "Chronic pain syndrome"),
    ("H26.9", "Unspecified cataract"),
    ("H40.10X0", "Open-angle glaucoma, unspecified, stage unspecified"),
    ("H61.23", "Impacted cerumen, bilateral"),
    ("H91.90", "Unspecified hearing loss, unspecified ear"),
    ("H93.19", "Tinnitus, unspecified ear"),
    ("H10.30", "Unspecified acute conjunctivitis, unspecified eye"),
    ("J30.9", "Allergic rhinitis, unspecified"),
    ("J32.9", "Chronic sinusitis, unspecified"),
    ("H66.90", "Otitis media, unspecified, unspecified ear"),
    ("K76.0", "Fatty (change of) liver, not elsewhere classified"),
    ("K74.60", "Unspecified cirrhosis of liver"),
    ("K80.20", "Calculus of gallbladder without cholecystitis without obstruction"),
    ("K86.1", "Other chronic pancreatitis"),
    ("K50.90", "Crohn disease of small intestine without complications"),
    ("K51.90", "Ulcerative colitis, unspecified, without complications"),
    ("B18.1", "Chronic viral hepatitis B without delta-agent"),
    ("B18.2", "Chronic viral hepatitis C"),
    ("B20", "Human immunodeficiency virus [HIV] disease"),
    ("A41.9", "Sepsis, unspecified organism"),
    ("A49.9", "Bacterial infection, unspecified"),
    ("S52.501A", "Unspecified fracture of lower end of radius, initial encounter"),
    ("S82.001A", "Unspecified fracture of right patella, initial encounter"),
    ("S93.401A", "Sprain of unspecified ligament of right ankle, initial encounter"),
    ("S40.011A", "Contusion of right shoulder, initial encounter"),
    ("T14.90", "Injury, unspecified"),
    ("S06.0X9A", "Concussion with loss of consciousness of unspecified duration, initial encounter"),
    ("Z00.00", "Encounter for general adult medical examination without abnormal findings"),
    ("Z00.01", "Encounter for general adult medical examination with abnormal findings"),
    ("Z12.11", "Encounter for screening for malignant neoplasm of colon"),
    ("Z12.31", "Encounter for screening mammogram for malignant neoplasm of breast"),
    ("Z23", "Encounter for immunization"),
    ("Z51.11", "Encounter for antineoplastic chemotherapy"),
    ("Z79.4", "Long-term (current) use of insulin"),
    ("Z79.01", "Long-term (current) use of anticoagulants"),
    ("Z87.39", "Personal history of other endocrine, nutritional and metabolic diseases"),
    ("I11.9", "Hypertensive heart disease without heart failure"),
    ("I12.9", "Hypertensive chronic kidney disease with stage 1 through stage 4 chronic kidney disease"),
    ("I13.10", "Hypertensive heart and chronic kidney disease without heart failure, with stage 1 through stage 4 chronic kidney disease"),
    ("R00.0", "Tachycardia, unspecified"),
    ("R00.1", "Bradycardia, unspecified"),
    ("R01.1", "Cardiac murmur, unspecified"),
    ("R03.0", "Elevated blood-pressure reading, without diagnosis of hypertension"),
    ("R07.9", "Chest pain, unspecified"),
    ("R13.10", "Dysphagia, unspecified"),
    ("R19.7", "Diarrhea, unspecified"),
    ("R25.2", "Cramp and spasm"),
    ("R41.3", "Other amnesia"),
    ("R45.1", "Restlessness and agitation"),
    ("R50.9", "Fever, unspecified"),
    ("R53.83", "Other fatigue"),
    ("R55", "Syncope and collapse"),
    ("R60.0", "Localized edema"),
    ("R68.89", "Other specified general symptoms and signs"),
    ("R73.09", "Other abnormal glucose"),
    ("R94.31", "Abnormal electrocardiogram [ECG] [EKG]"),
    ("Z96.641", "Presence of right artificial knee joint"),
    ("Z96.651", "Presence of right artificial hip joint"),
    ("Z95.0", "Presence of cardiac pacemaker"),
    ("Z95.1", "Presence of aortocoronary bypass graft"),
    ("M25.511", "Pain in right shoulder"),
    ("M25.512", "Pain in left shoulder"),
    ("M25.521", "Pain in right elbow"),
    ("M25.531", "Pain in right wrist"),
    ("M25.561", "Pain in right knee"),
    ("M25.571", "Pain in right ankle and joints of right foot"),
    ("M47.816", "Spondylosis without myelopathy or radiculopathy, lumbar region"),
    ("M48.06", "Spinal stenosis, lumbar region"),
    ("M23.61", "Other spontaneous disruption of anterior cruciate ligament of right knee"),
    ("M75.1", "Rotator cuff syndrome"),
    ("M77.11", "Lateral epicondylitis, right elbow"),
    ("M35.3", "Polymyalgia rheumatica"),
    ("M32.9", "Systemic lupus erythematosus, unspecified"),
    ("M34.9", "Systemic sclerosis, unspecified"),
    ("L89.90", "Pressure ulcer of unspecified site, unspecified stage"),
    ("L57.0", "Actinic keratosis"),
    ("L90.5", "Scar conditions and fibrosis of skin"),
    ("L70.0", "Acne vulgaris"),
    ("L60.0", "Ingrowing nail"),
    ("B35.1", "Tinea unguium"),
    ("B00.9", "Herpesviral infection, unspecified"),
    ("B02.9", "Zoster without complications"),
    ("K04.7", "Periapical abscess without sinus"),
    ("K08.409", "Partial loss of teeth, unspecified cause, unspecified class"),
    ("N17.9", "Acute kidney failure, unspecified"),
    ("N30.00", "Acute cystitis without hematuria"),
    ("N41.0", "Acute prostatitis"),
    ("N46.01", "Organic azoospermia"),
    ("N94.10", "Unspecified dyspareunia"),
    ("O09.90", "Supervision of high risk pregnancy, unspecified, unspecified trimester"),
    ("O26.50", "Maternal hypotension syndrome, unspecified trimester"),
    ("O99.320", "Obesity complicating pregnancy, unspecified trimester"),
    ("P07.17", "Extreme immaturity of newborn, gestational age 27 completed weeks"),
    ("Q21.0", "Ventricular septal defect"),
    ("Q65.01", "Congenital dislocation of right hip, unilateral"),
    ("R11.0", "Nausea"),
    ("R11.10", "Vomiting, unspecified"),
    ("R14.0", "Abdominal distension (gaseous)"),
    ("R16.0", "Hepatomegaly, not elsewhere classified"),
    ("R20.0", "Anaesthesia of skin"),
    ("R23.1", "Flushing"),
    ("R26.89", "Other abnormalities of gait and mobility"),
    ("R29.0", "Tetany"),
    ("R33.9", "Retention of urine, unspecified"),
    ("R35.0", "Frequency of micturition"),
    ("R39.15", "Urgency of urination"),
    ("R56.9", "Unspecified convulsions"),
    ("R63.0", "Anorexia"),
    ("R63.4", "Abnormal weight loss"),
    ("R63.5", "Abnormal weight gain"),
    ("R65.10", "Systemic inflammatory response syndrome of non-infectious origin without acute organ dysfunction"),
    ("R79.89", "Other specified abnormal findings of blood chemistry"),
    ("S01.00XA", "Unspecified open wound of scalp, initial encounter"),
    ("S09.90XA", "Unspecified injury of head, initial encounter"),
    ("S20.01XA", "Contusion of breast, right side, initial encounter"),
    ("S29.9XXA", "Unspecified injury of thorax, initial encounter"),
    ("S39.9XXA", "Unspecified injury of abdomen, initial encounter"),
    ("S49.90XA", "Physeal fracture of unspecified part of upper end of unspecified humerus, initial encounter"),
    ("S59.209A", "Unspecified physeal fracture of lower end of unspecified radius, initial encounter"),
    ("S69.90XA", "Unspecified injury of unspecified wrist and hand, initial encounter"),
    ("S79.919A", "Unspecified injury of unspecified hip, initial encounter"),
    ("S89.90XA", "Unspecified injury of unspecified lower leg, initial encounter"),
    ("T36.0X5A", "Adverse effect of penicillins, initial encounter"),
    ("T39.1X5A", "Adverse effect of 4-Aminophenol derivatives, initial encounter"),
    ("T45.515A", "Adverse effect of anticoagulants, initial encounter"),
    ("T78.40XA", "Allergy, unspecified, initial encounter"),
    ("T78.1XXA", "Other adverse food reactions, not elsewhere classified, initial encounter"),
    ("U09.9", "Post-COVID-19 condition, unspecified"),
    ("Z00.121", "Encounter for routine child health examination with abnormal findings"),
    ("Z02.89", "Encounter for other administrative examinations"),
    ("Z13.220", "Encounter for screening for lipoid disorders"),
    ("Z13.6", "Encounter for screening for cardiovascular disorders"),
    ("Z13.810", "Encounter for screening for upper gastrointestinal disorder"),
    ("Z79.82", "Long-term (current) use of aspirin"),
    ("Z79.84", "Long-term (current) use of oral hypoglycemic drugs"),
    ("Z79.899", "Other long-term (current) drug therapy"),
    ("Z82.49", "Family history of ischemic heart disease and other diseases of the circulatory system"),
    ("Z85.118", "Personal history of other malignant neoplasm of bronchus and lung"),
    ("Z86.010", "Personal history of colonic polyps"),
    ("Z87.11", "Personal history of peptic ulcer disease"),
    ("Z87.442", "Personal history of urinary calculi"),
    ("Z96.21", "Presence of intraocular lens"),
    ("Z98.890", "Other specified postprocedural states"),
    ("A15.0", "Tuberculosis of lung"),
    ("A37.90", "Whooping cough, unspecified species without pneumonia"),
    ("A69.20", "Lyme disease, unspecified"),
    ("B19.20", "Unspecified viral hepatitis C without hepatic coma"),
    ("C56.1", "Malignant neoplasm of right ovary"),
    ("C67.9", "Malignant neoplasm of bladder, unspecified"),
    ("C79.51", "Secondary malignant neoplasm of bone"),
    ("D05.10", "Intraductal carcinoma in situ of right breast"),
    ("D25.9", "Leiomyoma of uterus, unspecified"),
    ("E04.1", "Nontoxic single thyroid nodule"),
    ("E21.0", "Primary hyperparathyroidism"),
    ("E27.49", "Other adrenocortical insufficiency"),
    ("E28.2", "Polycystic ovarian syndrome"),
    ("E86.0", "Dehydration"),
    ("F50.00", "Anorexia nervosa, unspecified"),
    ("F50.2", "Bulimia nervosa"),
    ("F60.3", "Borderline personality disorder"),
    ("G00.9", "Bacterial meningitis, unspecified"),
    ("G11.19", "Other early-onset cerebellar ataxia"),
    ("G47.33", "Obstructive sleep apnea (adult) (pediatric)"),
    ("G47.00", "Insomnia, unspecified"),
    ("G57.00", "Lesion of sciatic nerve, unspecified lower limb"),
    ("H00.014", "Hordeolum externum left upper eyelid"),
    ("H25.11", "Age-related nuclear cataract, right eye"),
    ("H53.10", "Unspecified subjective visual disturbances"),
    ("I34.0", "Nonrheumatic mitral (valve) insufficiency"),
    ("I35.0", "Nonrheumatic aortic (valve) stenosis"),
    ("I71.4", "Abdominal aortic aneurysm, without rupture"),
    ("I84.1", "Internal thrombosed hemorrhoids without complication"),
    ("J38.5", "Laryngeal spasm"),
    ("J69.0", "Pneumonitis due to inhalation of food and vomit"),
    ("J96.00", "Acute respiratory failure, unspecified whether with hypoxia or hypercapnia"),
    ("K43.9", "Ventral hernia without obstruction or gangrene"),
    ("K56.60", "Unspecified intestinal obstruction, unspecified as to partial versus complete obstruction"),
    ("K63.5", "Polyp of colon"),
    ("K85.10", "Biliary acute pancreatitis without necrosis or infection"),
    ("L03.314", "Cellulitis of chest wall"),
    ("L08.9", "Local infection of the skin and subcutaneous tissue, unspecified"),
    ("M05.79", "Rheumatoid arthritis with rheumatoid factor of multiple sites without organ or systems involvement"),
    ("M13.9", "Arthritis, unspecified"),
    ("M24.651", "Contracture, right hip"),
    ("M51.16", "Intervertebral disc degeneration, lumbar region"),
    ("M65.31", "Trigger finger, right thumb"),
    ("M71.31", "Other bursitis of right shoulder"),
    ("N13.30", "Unspecified hydronephrosis"),
    ("N35.919", "Unspecified urethral stricture, unspecified, not elsewhere classified"),
    ("N60.01", "Solitary cyst of right breast"),
    ("N63.0", "Unspecified lump in unspecified breast"),
    ("N95.1", "Menopausal and female climacteric states"),
    ("O10.012", "Pre-existing essential hypertension complicating pregnancy, second trimester"),
    ("R00.8", "Other abnormalities of heart beat"),
    ("R04.2", "Haemoptysis"),
    ("R09.02", "Hypoxemia"),
    ("R17", "Unspecified jaundice"),
    ("R21", "Rash and other nonspecific skin eruption"),
    ("R25.1", "Tremor, unspecified"),
    ("R27.0", "Ataxia, unspecified"),
    ("R30.0", "Dysuria"),
    ("R31.9", "Hematuria, unspecified"),
    ("R40.20", "Unspecified coma"),
    ("R47.00", "Unspecified speech disturbances"),
    ("R52", "Pain, unspecified"),
    ("R57.0", "Cardiogenic shock"),
    ("R61", "Generalized hyperhidrosis"),
    ("R68.13", "Apparent life threatening event in infant (ALTE)"),
    ("R70.0", "Elevated erythrocyte sedimentation rate"),
    ("R74.01", "Elevation of levels of liver transaminase levels"),
    ("R77.1", "Abnormality of globulin"),
    ("S00.00XA", "Unspecified superficial injury of scalp, initial encounter"),
    ("S01.80XA", "Open wound of unspecified head part, initial encounter"),
    ("S10.93XA", "Unspecified superficial injury of neck, initial encounter"),
    ("S20.00XA", "Unspecified superficial injury of breast, initial encounter"),
    ("S30.1XXA", "Contusion of abdominal wall, initial encounter"),
    ("T07", "Unspecified multiple injuries"),
    ("T14.8", "Other injury of unspecified body region"),
    ("Z04.89", "Encounter for examination and observation for other specified reasons"),
    ("Z11.3", "Encounter for screening examination for infections with a predominantly sexual mode of transmission"),
    ("Z11.59", "Encounter for screening for other viral diseases"),
    ("Z13.31", "Encounter for screening examination for hearing loss"),
    ("Z13.5", "Encounter for screening for eye and ear disorders"),
    ("Z13.89", "Encounter for screening for other disorder"),
    ("Z71.3", "Dietary counseling and surveillance"),
    ("Z76.89", "Persons encountering health services in other specified circumstances"),
    ("Z96.641", "Presence of right artificial knee joint"),
    ("Z98.891", "Other specified postprocedural states"),
]

TEMPLATES = [
    {
        "name": "General New Patient Evaluation",
        "system_prompt": (
            "This is a comprehensive new patient evaluation. "
            "The SOAP note should be thorough and include: full medical, surgical, family, and social history in Subjective; "
            "complete vital signs and systematic physical exam in Objective; "
            "a detailed assessment with primary and secondary diagnoses; "
            "a complete care plan including labs, imaging, referrals, and follow-up. "
            "This is likely a patient's first visit, so establish baseline thoroughly."
        ),
    },
    {
        "name": "Orthopedic Follow-Up",
        "system_prompt": (
            "This is an orthopedic follow-up visit. "
            "Focus on: musculoskeletal symptoms, pain scale (0-10), ROM assessment, functional limitations, "
            "response to prior treatments (PT, medications, injections, surgery), "
            "imaging findings if available. "
            "Plan should address conservative vs. interventional options, PT orders, and surgical candidacy if relevant. "
            "Use musculoskeletal ICD-10 codes (M-codes) as primary diagnoses."
        ),
    },
    {
        "name": "Urgent Care / Acute Visit",
        "system_prompt": (
            "This is an urgent care or acute illness visit. "
            "Be concise and action-oriented. Focus on: chief complaint, onset/duration/severity, "
            "relevant acute exam findings, and a targeted differential. "
            "Plan should include immediate interventions, prescriptions with specific dosages if applicable, "
            "clear return precautions, and when to escalate to ED. "
            "Avoid extensive chronic disease review unless directly relevant."
        ),
    },
    {
        "name": "Chronic Disease Management",
        "system_prompt": (
            "This is a chronic disease management visit. "
            "Focus on: disease control metrics (HbA1c, BP readings, peak flow, etc.), "
            "medication adherence and side effects, lifestyle factors, "
            "complications screening. "
            "Assessment should grade disease control (well-controlled/poorly-controlled). "
            "Plan should include medication adjustments, lab orders, specialist coordination, and patient education. "
            "Use chronic disease ICD-10 codes with appropriate specificity."
        ),
    },
]

PROVIDERS = [
    {
        "first_name": "Sarah",
        "last_name": "Chen",
        "email": "dr.chen@scribe.demo",
        "password": "Provider1!",
        "role": "provider",
    },
    {
        "first_name": "Marcus",
        "last_name": "Williams",
        "email": "dr.williams@scribe.demo",
        "password": "Provider2!",
        "role": "provider",
    },
    {
        "first_name": "Elena",
        "last_name": "Rodriguez",
        "email": "dr.rodriguez@scribe.demo",
        "password": "Provider3!",
        "role": "provider",
    },
    {
        "first_name": "Admin",
        "last_name": "User",
        "email": "admin@scribe.demo",
        "password": "Admin123!",
        "role": "admin",
    },
]


def run_seed():
    print("Creating tables...")
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Seed providers
        existing_providers = db.query(models.Provider).count()
        if existing_providers == 0:
            print("Seeding providers...")
            for p in PROVIDERS:
                provider = models.Provider(
                    first_name=p["first_name"],
                    last_name=p["last_name"],
                    email=p["email"],
                    password_hash=hash_password(p["password"]),
                    role=models.RoleEnum(p["role"]),
                    is_active=True,
                )
                db.add(provider)
            db.commit()
            print(f"  Added {len(PROVIDERS)} providers")
        else:
            print(f"  Providers already exist ({existing_providers}), skipping")

        # Seed templates
        existing_templates = db.query(models.Template).count()
        if existing_templates == 0:
            print("Seeding templates...")
            for t in TEMPLATES:
                template = models.Template(
                    name=t["name"],
                    system_prompt=t["system_prompt"],
                    is_active=True,
                )
                db.add(template)
            db.commit()
            print(f"  Added {len(TEMPLATES)} templates")
        else:
            print(f"  Templates already exist ({existing_templates}), skipping")

        # Seed ICD-10 codes
        existing_codes = db.query(models.ICD10Code).count()
        if existing_codes == 0:
            print(f"Seeding {len(ICD10_CODES)} ICD-10 codes with embeddings...")
            for i, (code, description) in enumerate(ICD10_CODES):
                embedding = embed_description(description)
                icd = models.ICD10Code(
                    code=code,
                    description=description,
                    embedding=embedding,
                )
                db.add(icd)
                if (i + 1) % 50 == 0:
                    db.commit()
                    print(f"  {i+1}/{len(ICD10_CODES)} codes committed")
            db.commit()
            print(f"  All {len(ICD10_CODES)} ICD-10 codes seeded")
        else:
            print(f"  ICD-10 codes already exist ({existing_codes}), skipping")

        print("\nSeed complete!")
        print("\nDemo accounts:")
        for p in PROVIDERS:
            print(f"  {p['role'].upper()}: {p['email']} / {p['password']}")

    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
