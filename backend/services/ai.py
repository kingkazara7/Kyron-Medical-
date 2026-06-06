import json
import anthropic
from typing import Generator, Optional
from sqlalchemy.orm import Session
from models import Patient, Encounter, Note, NoteVersion, Template
from config import get_settings

settings = get_settings()

INSUFFICIENT_RESPONSE = {
    "subjective": "Insufficient clinical content provided.",
    "objective": "No objective findings documented.",
    "assessment": "Unable to generate assessment — insufficient clinical data.",
    "plan": "Please provide a complete clinical transcript to generate a care plan.",
    "icd10_codes": []
}

CLINICAL_KEYWORDS = [
    "pain", "ache", "fever", "cough", "nausea", "vomit", "bleed", "dyspnea",
    "breath", "chest", "abdomen", "head", "dizziness", "fatigue", "swollen",
    "rash", "history", "medication", "diagnosis", "complaint", "symptom",
    "patient", "exam", "bp", "pulse", "temp", "hr ", "rr ", "o2", "spo2",
    "heart", "lung", "edema", "hypertension", "diabetes", "asthma", "copd",
    "follow", "visit", "treatment", "prescribed", "imaging", "lab", "x-ray",
    "mri", "ct ", "ekg", "ecg", "blood", "urine", "infection", "fracture",
    "laceration", "sprain", "strain", "allergy", "review", "presenting"
]

def has_clinical_content(text: str) -> bool:
    lower = text.lower()
    return sum(1 for kw in CLINICAL_KEYWORDS if kw in lower) >= 2

def get_patient_history_tool_def():
    return {
        "name": "get_patient_history",
        "description": "Retrieve prior encounter history for a patient to use as clinical context. Call this when you need to reference past diagnoses, treatments, or clinical findings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "integer",
                    "description": "The patient ID"
                }
            },
            "required": ["patient_id"]
        }
    }

def fetch_patient_history(patient_id: int, db: Session, exclude_encounter_id: Optional[int] = None) -> str:
    patient = db.get(Patient, patient_id)
    if not patient:
        return "No patient found."
    encounters = (
        db.query(Encounter)
        .filter(
            Encounter.patient_id == patient_id,
            Encounter.status == "saved"
        )
        .order_by(Encounter.created_at.desc())
        .limit(5)
        .all()
    )
    if not encounters:
        return f"No prior encounters on file for {patient.first_name} {patient.last_name} (DOB: {patient.dob})."

    history_parts = [f"Patient: {patient.first_name} {patient.last_name}, DOB: {patient.dob}\n"]
    history_parts.append(f"Prior encounters ({len(encounters)}):\n")
    for enc in encounters:
        if exclude_encounter_id and enc.id == exclude_encounter_id:
            continue
        if enc.note and enc.note.versions:
            latest_ver = enc.note.versions[-1]
            content = latest_ver.content
            codes_str = ", ".join(
                c.get("code", "") + " " + c.get("description", "")
                for c in content.get("icd10_codes", [])
            )
            history_parts.append(
                f"\n--- Encounter {enc.id} ({enc.created_at.date()}) ---\n"
                f"Assessment: {content.get('assessment', 'N/A')}\n"
                f"Plan: {content.get('plan', 'N/A')}\n"
                f"ICD-10: {codes_str}\n"
            )
    return "".join(history_parts)

def stream_soap_note(
    transcript: str,
    patient_id: int,
    encounter_id: int,
    template: Optional[Template],
    db: Session
) -> Generator[str, None, None]:
    if not has_clinical_content(transcript):
        yield f"data: {json.dumps({'type': 'content', 'text': json.dumps(INSUFFICIENT_RESPONSE)})}\n\n"
        yield "data: [DONE]\n\n"
        return

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    base_system = (
        "You are an expert clinical documentation AI for a medical practice. "
        "Generate structured SOAP notes from clinical transcripts or observations.\n\n"
        "Always respond with valid JSON in this exact format:\n"
        "{\n"
        '  "subjective": "Patient\'s chief complaint and history...",\n'
        '  "objective": "Vital signs, physical exam findings...",\n'
        '  "assessment": "Clinical impression and diagnoses...",\n'
        '  "plan": "Treatment plan, medications, follow-up...",\n'
        '  "icd10_codes": [{"code": "X00.0", "description": "Diagnosis"}]\n'
        "}\n\n"
        "Include 1-3 ICD-10 codes semantically matched to the clinical content. "
        "Be precise, clinical, and use appropriate medical terminology."
    )

    template_addendum = ""
    if template:
        template_addendum = f"\n\nEncounter Template — {template.name}:\n{template.system_prompt}"

    system_prompt = base_system + template_addendum

    messages = [
        {
            "role": "user",
            "content": (
                f"Generate a SOAP note. First retrieve patient history if they are returning.\n\n"
                f"Patient ID: {patient_id}\nEncounter ID: {encounter_id}\n\n"
                f"Transcript/Observations:\n{transcript}"
            )
        }
    ]

    tools = [get_patient_history_tool_def()]

    while True:
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=system_prompt,
            messages=messages,
            tools=tools,
        ) as stream:
            response_text = ""
            tool_calls = []
            current_tool = None

            for event in stream:
                if event.type == "content_block_start":
                    if hasattr(event.content_block, "type"):
                        if event.content_block.type == "tool_use":
                            current_tool = {
                                "id": event.content_block.id,
                                "name": event.content_block.name,
                                "input": ""
                            }
                elif event.type == "content_block_delta":
                    if hasattr(event.delta, "type"):
                        if event.delta.type == "text_delta":
                            response_text += event.delta.text
                            yield f"data: {json.dumps({'type': 'text', 'text': event.delta.text})}\n\n"
                        elif event.delta.type == "input_json_delta":
                            if current_tool:
                                current_tool["input"] += event.delta.partial_json
                elif event.type == "content_block_stop":
                    if current_tool:
                        tool_calls.append(current_tool)
                        current_tool = None

            final_message = stream.get_final_message()

            if final_message.stop_reason == "tool_use" and tool_calls:
                tool_results = []
                for tc in tool_calls:
                    if tc["name"] == "get_patient_history":
                        try:
                            tool_input = json.loads(tc["input"]) if tc["input"] else {}
                            pid = tool_input.get("patient_id", patient_id)
                        except Exception:
                            pid = patient_id
                        history = fetch_patient_history(pid, db, exclude_encounter_id=encounter_id)
                        yield f"data: {json.dumps({'type': 'tool_result', 'tool': 'get_patient_history', 'summary': 'Retrieved patient history'})}\n\n"
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc["id"],
                            "content": history
                        })

                messages.append({"role": "assistant", "content": final_message.content})
                messages.append({"role": "user", "content": tool_results})
            else:
                break

    yield "data: [DONE]\n\n"


def search_icd10_semantic(query: str, db: Session, top_k: int = 8):
    from models import ICD10Code
    from services.icd10_embeddings import get_query_embedding, cosine_similarity

    codes = db.query(ICD10Code).filter(ICD10Code.embedding.isnot(None)).all()
    if not codes:
        return []

    query_emb = get_query_embedding(query)
    scored = []
    for code in codes:
        emb = code.embedding
        if emb:
            sim = cosine_similarity(query_emb, emb)
            scored.append((sim, code))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"code": c.code, "description": c.description, "score": round(float(s), 4)}
        for s, c in scored[:top_k]
    ]
