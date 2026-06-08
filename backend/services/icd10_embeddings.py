"""
ICD-10 semantic embeddings using fastembed (ONNX, CPU-only, no PyTorch).

Model: BAAI/bge-small-en-v1.5
  - 384-dim dense vectors
  - ~60 MB on disk, ~150 MB RAM
  - Proper semantic understanding (light sensitivity → migraine, not asthma)
"""
from typing import List
import numpy as np

_model = None


def _get_model():
    global _model
    if _model is None:
        try:
            from fastembed import TextEmbedding
            _model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        except Exception:
            # Fallback: original bag-of-words if fastembed unavailable
            _model = "fallback"
    return _model


def embed_description(description: str) -> List[float]:
    model = _get_model()
    if model == "fallback":
        return _bow_embed(description)
    embeddings = list(model.embed([description]))
    return embeddings[0].tolist()


def get_query_embedding(text: str) -> List[float]:
    return embed_description(text)


def cosine_similarity(a: List[float], b: List[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


# ── Fallback: bag-of-words (used only if fastembed fails to load) ──────────

def _bow_embed(text: str) -> List[float]:
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
            "thoracic", "radiculopathy", "neuropathy", "seizure", "epilepsy",
            "parkinson", "alzheimer", "dementia", "multiple", "sclerosis",
            "cancer", "malignant", "neoplasm", "benign", "tumor", "lymphoma",
            "leukemia", "breast", "colon", "lung", "melanoma", "carcinoma",
            "sepsis", "shock", "inflammatory", "autoimmune", "allergy", "allergic",
            "rhinitis", "sinusitis", "otitis", "glaucoma", "cataract", "conjunctivitis",
            "hearing", "loss", "tinnitus", "pregnancy", "obstetric", "menstrual",
            "ovarian", "uterine", "endometriosis", "glycemia", "insulin", "metabolic",
            "dehydration", "muscle", "weakness", "fibromyalgia", "fatigue",
            "post", "covid", "viral", "bacterial", "hiv", "hepatitis", "cirrhosis",
            "alcohol", "opioid", "tobacco", "bipolar", "schizophrenia", "adhd",
            "autism", "obsessive", "compulsive", "ptsd", "panic",
        ]
        _get_vocab._cache = {w: i for i, w in enumerate(set(words))}
    return _get_vocab._cache
