import numpy as np
from typing import List


def get_query_embedding(text: str) -> List[float]:
    """Simple TF-IDF-style keyword embedding for ICD-10 search."""
    tokens = text.lower().split()
    vocab_map = _get_vocab()
    vec = np.zeros(len(vocab_map))
    for token in tokens:
        if token in vocab_map:
            vec[vocab_map[token]] += 1.0
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def cosine_similarity(a: List[float], b: List[float]) -> float:
    va = np.array(a)
    vb = np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def embed_description(description: str) -> List[float]:
    return get_query_embedding(description)


def _get_vocab():
    if not hasattr(_get_vocab, "_cache"):
        words = [
            "pain", "acute", "chronic", "unspecified", "infection", "disease",
            "disorder", "syndrome", "type", "essential", "primary", "secondary",
            "hypertension", "diabetes", "mellitus", "failure", "heart", "cardiac",
            "respiratory", "pulmonary", "asthma", "copd", "pneumonia", "bronchitis",
            "influenza", "fever", "cough", "dyspnea", "chest", "back", "neck",
            "abdominal", "joint", "knee", "hip", "shoulder", "arm", "leg", "foot",
            "head", "migraine", "headache", "dizziness", "vertigo", "anxiety",
            "depression", "disorder", "mental", "sleep", "insomnia", "fatigue",
            "nausea", "vomiting", "diarrhea", "constipation", "gastrointestinal",
            "gastric", "ulcer", "reflux", "esophageal", "hepatic", "liver",
            "kidney", "renal", "urinary", "bladder", "prostate", "thyroid",
            "hypothyroid", "hyperthyroid", "anemia", "iron", "deficiency",
            "vitamin", "obesity", "overweight", "hyperlipidemia", "cholesterol",
            "atrial", "fibrillation", "arrhythmia", "coronary", "artery",
            "myocardial", "infarction", "stroke", "cerebrovascular", "peripheral",
            "vascular", "deep", "vein", "thrombosis", "cellulitis", "dermatitis",
            "eczema", "psoriasis", "skin", "wound", "laceration", "fracture",
            "sprain", "strain", "injury", "trauma", "concussion", "osteoarthritis",
            "rheumatoid", "arthritis", "gout", "osteoporosis", "lumbar", "cervical",
            "thoracic", "radiculopathy", "neuropathy", "peripheral", "autonomic",
            "seizure", "epilepsy", "parkinson", "alzheimer", "dementia",
            "multiple", "sclerosis", "cancer", "malignant", "neoplasm", "benign",
            "tumor", "lymphoma", "leukemia", "breast", "prostate", "colon",
            "lung", "skin", "melanoma", "basal", "cell", "carcinoma", "urinary",
            "tract", "sepsis", "septic", "shock", "inflammatory", "autoimmune",
            "allergy", "allergic", "rhinitis", "sinusitis", "otitis", "ear",
            "eye", "glaucoma", "cataract", "retinal", "conjunctivitis",
            "hearing", "loss", "tinnitus", "dental", "oral", "oral",
            "pregnancy", "prenatal", "postpartum", "obstetric", "gynecologic",
            "menstrual", "ovarian", "uterine", "cervical", "endometriosis",
            "erectile", "sexual", "dysfunction", "testosterone", "estrogen",
            "hypo", "hyper", "glycemia", "insulin", "resistance", "metabolic",
            "obesity", "morbid", "bmi", "weight", "nutrition", "malnutrition",
            "dehydration", "electrolyte", "sodium", "potassium", "calcium",
            "muscle", "weakness", "myopathy", "fibromyalgia", "chronic",
            "fatigue", "syndrome", "post", "covid", "viral", "bacterial",
            "fungal", "parasitic", "hiv", "aids", "hepatitis", "cirrhosis",
            "alcohol", "substance", "abuse", "dependence", "opioid", "tobacco",
            "smoking", "nicotine", "addiction", "detox", "withdrawal",
            "suicidal", "ideation", "self", "harm", "bipolar", "schizophrenia",
            "adhd", "autism", "spectrum", "obsessive", "compulsive", "ptsd",
            "post", "traumatic", "stress", "social", "phobia", "panic",
        ]
        _get_vocab._cache = {w: i for i, w in enumerate(sorted(set(words)))}
    return _get_vocab._cache
