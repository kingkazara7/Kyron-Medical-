import json
import anthropic
from typing import Generator, Optional
from sqlalchemy.orm import Session, joinedload
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

ANCHOR_TERMS = [
    "patient", "presenting", "complaint", "history", "diagnosis",
    "exam", "visit", "follow", "assessment", "treatment", "encounter"
]

def has_clinical_content(text: str) -> bool:
    lower = text.lower()
    words = lower.split()
    # Must have enough words to contain real clinical content
    if len(words) < 10:
        return False
    # Must have at least 3 clinical keyword matches
    if sum(1 for kw in CLINICAL_KEYWORDS if kw in lower) < 3:
        return False
    # Must have at least one anchor term indicating a clinical encounter
    return any(a in lower for a in ANCHOR_TERMS)

def get_patient_history_tool_def():
    return {
        "name": "get_patient_history",
        "description": (
            "Retrieve this patient's full prior encounter history from the database. "
            "Always call this tool first before generating any SOAP note. "
            "For new patients it will confirm no prior history exists. "
            "For returning patients it provides past diagnoses, treatments, and ICD-10 codes "
            "that should be referenced where clinically relevant in the new note."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "patient_id": {
                    "type": "integer",
                    "description": "The patient ID to look up"
                }
            },
            "required": ["patient_id"]
        }
    }

def fetch_patient_history(patient_id: int, db: Session, exclude_encounter_id: Optional[int] = None) -> str:
    """
    Returns a structured summary of all prior *saved* encounters for the patient.
    Eagerly loads note versions to avoid lazy-load issues inside the SSE generator.
    """
    patient = db.get(Patient, patient_id)
    if not patient:
        return "No patient found with that ID."

    encounters = (
        db.query(Encounter)
        .options(
            joinedload(Encounter.note).joinedload(Note.versions)
        )
        .filter(
            Encounter.patient_id == patient_id,
            Encounter.status == "saved",
        )
        .order_by(Encounter.created_at.desc())
        .limit(5)
        .all()
    )

    # Filter out the current encounter (being generated right now)
    prior = [e for e in encounters if e.id != exclude_encounter_id]

    if not prior:
        return (
            f"FIRST-TIME PATIENT — No prior saved encounters on file for "
            f"{patient.first_name} {patient.last_name} (DOB: {patient.dob}). "
            f"Generate the SOAP note based solely on the current transcript."
        )

    parts = [
        f"RETURNING PATIENT — {patient.first_name} {patient.last_name} (DOB: {patient.dob})\n"
        f"{len(prior)} prior encounter(s) retrieved. Reference relevant history in the new note.\n"
    ]

    for enc in prior:
        if not enc.note or not enc.note.versions:
            continue
        latest = enc.note.versions[-1].content
        codes_str = ", ".join(
            f"{c.get('code','')} ({c.get('description','')})"
            for c in latest.get("icd10_codes", [])
        ) or "None recorded"

        parts.append(
            f"\n=== Encounter on {enc.created_at.date()} ===\n"
            f"Assessment: {latest.get('assessment', 'N/A')}\n"
            f"Plan:       {latest.get('plan', 'N/A')}\n"
            f"ICD-10:     {codes_str}\n"
            f"Subjective: {latest.get('subjective', 'N/A')[:300]}\n"
        )

    return "".join(parts)


def stream_soap_note(
    transcript: str,
    patient_id: int,
    encounter_id: int,
    template,          # SimpleNamespace or None
    db: Session
) -> Generator[str, None, None]:

    if not has_clinical_content(transcript):
        yield f"data: {json.dumps({'type': 'insufficient', 'note': INSUFFICIENT_RESPONSE})}\n\n"
        yield "data: [DONE]\n\n"
        return

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    base_system = (
        "You are an expert clinical documentation AI. "
        "Your job is to generate structured SOAP notes from encounter transcripts.\n\n"
        "MANDATORY FIRST STEP: You must ALWAYS call the get_patient_history tool before "
        "writing any SOAP content. This retrieves the patient's database record. "
        "For first-time patients it will say so. For returning patients it will provide "
        "prior diagnoses and treatments that you MUST reference where clinically relevant.\n\n"
        "After the tool returns, output ONLY valid JSON in this exact format — no preamble, "
        "no explanation, no markdown:\n"
        "{\n"
        '  "subjective": "...",\n'
        '  "objective": "...",\n'
        '  "assessment": "...",\n'
        '  "plan": "...",\n'
        '  "icd10_codes": [{"code": "X00.0", "description": "Diagnosis name"}]\n'
        "}\n\n"
        "Include 1-3 ICD-10 codes matched to the clinical content. "
        "Be precise and use appropriate medical terminology."
    )

    if template:
        base_system += f"\n\nEncounter Template — {template.name}:\n{template.system_prompt}"

    messages = [
        {
            "role": "user",
            "content": (
                f"Generate a SOAP note for this encounter.\n\n"
                f"Patient ID: {patient_id}\n"
                f"Encounter ID: {encounter_id}\n\n"
                f"Transcript/Observations:\n{transcript}"
            )
        }
    ]

    tools = [get_patient_history_tool_def()]

    while True:
        with client.messages.stream(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            system=base_system,
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
