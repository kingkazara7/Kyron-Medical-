#!/usr/bin/env python3
"""
Fix non-happy-path AI output handling:
1. Backend: strengthen has_clinical_content (word count + anchor requirement)
2. Backend: send type='insufficient' instead of type='content' so frontend can distinguish
3. Frontend: show prominent warning banner for insufficient content
4. Frontend: detect stream-ended-with-no-json (AI text refusal) and show error
"""

# ─── BACKEND: services/ai.py ─────────────────────────────────────────────────
ai_path = '/home/ubuntu/scribe/backend/services/ai.py'
with open(ai_path) as f:
    ai = f.read()

changes_be = 0

def rep_be(old, new, label):
    global ai, changes_be
    if old in ai:
        ai = ai.replace(old, new, 1)
        changes_be += 1
        print(f'Backend OK: {label}')
    else:
        print(f'Backend WARN not found: {label}')

# 1. Strengthen has_clinical_content
rep_be(
    'def has_clinical_content(text: str) -> bool:\n'
    '    lower = text.lower()\n'
    '    return sum(1 for kw in CLINICAL_KEYWORDS if kw in lower) >= 2',

    'ANCHOR_TERMS = [\n'
    '    "patient", "presenting", "complaint", "history", "diagnosis",\n'
    '    "exam", "visit", "follow", "assessment", "treatment", "encounter"\n'
    ']\n'
    '\n'
    'def has_clinical_content(text: str) -> bool:\n'
    '    lower = text.lower()\n'
    '    words = lower.split()\n'
    '    # Must have enough words to contain real clinical content\n'
    '    if len(words) < 10:\n'
    '        return False\n'
    '    # Must have at least 3 clinical keyword matches\n'
    '    if sum(1 for kw in CLINICAL_KEYWORDS if kw in lower) < 3:\n'
    '        return False\n'
    '    # Must have at least one anchor term indicating a clinical encounter\n'
    '    return any(a in lower for a in ANCHOR_TERMS)',
    'strengthen has_clinical_content'
)

# 2. Send type='insufficient' instead of type='content' so frontend can distinguish
rep_be(
    '        yield f"data: {json.dumps({\'type\': \'content\', \'text\': json.dumps(INSUFFICIENT_RESPONSE)})}\\n\\n"\n'
    '        yield "data: [DONE]\\n\\n"\n'
    '        return',

    '        yield f"data: {json.dumps({\'type\': \'insufficient\', \'note\': INSUFFICIENT_RESPONSE})}\\n\\n"\n'
    '        yield "data: [DONE]\\n\\n"\n'
    '        return',
    'send type=insufficient event'
)

with open(ai_path, 'w') as f:
    f.write(ai)

print(f'Backend: {changes_be} changes applied.\n')

# ─── FRONTEND: Workspace.jsx ──────────────────────────────────────────────────
ws_path = '/home/ubuntu/scribe/frontend/src/pages/Workspace.jsx'
with open(ws_path) as f:
    ws = f.read()

changes_fe = 0

def rep_fe(old, new, label):
    global ws, changes_fe
    if old in ws:
        ws = ws.replace(old, new, 1)
        changes_fe += 1
        print(f'Frontend OK: {label}')
    else:
        print(f'Frontend WARN not found: {label}')

# 3. Handle type='insufficient' → show warning banner, set note, do NOT mark dirty
#    Also: after [DONE], if no valid JSON was ever parsed → show error
#    Original SSE loop has:
#    if (raw === '[DONE]') { setStreamStatus(''); break; }
#    ...
#    } else if (evt.type === 'content') {
#      try { const p = JSON.parse(evt.text); setNote(p); } catch {}
#    }

# Step A: Add a soapGenerated flag tracking and handle type='insufficient'
rep_fe(
    "      while (true) {\n"
    "        const { done, value } = await reader.read();\n"
    "        if (done) break;\n"
    "        sseBuffer += decoder.decode(value, { stream: true });\n"
    "        const lines = sseBuffer.split('\\n');\n"
    "        sseBuffer = lines.pop() || '';\n"
    "        for (const line of lines) {\n"
    "          if (!line.startsWith('data: ')) continue;\n"
    "          const raw = line.slice(6).trim();\n"
    "          if (raw === '[DONE]') { setStreamStatus(''); break; }\n"
    "          try {\n"
    "            const evt = JSON.parse(raw);\n"
    "            if (evt.type === 'tool_result') {\n"
    "              setStreamStatus('Retrieved patient history…');\n"
    "              accumulated = '';\n"
    "            } else if (evt.type === 'text') {\n"
    "              accumulated += evt.text;\n"
    "              const partial = extractPartialFields(accumulated);\n"
    "              if (Object.keys(partial).length > 0) setNote(prev => ({ ...prev, ...partial }));\n"
    "              const j0 = accumulated.indexOf('{'), j1 = accumulated.lastIndexOf('}');\n"
    "              if (j0 !== -1 && j1 > j0) {\n"
    "                try {\n"
    "                  const parsed = JSON.parse(accumulated.slice(j0, j1 + 1));\n"
    "                  if (parsed.subjective !== undefined) { setNote(parsed); saveDraft(parsed); }\n"
    "                } catch {}\n"
    "              }\n"
    "            } else if (evt.type === 'content') {\n"
    "              try { const p = JSON.parse(evt.text); setNote(p); } catch {}\n"
    "            }\n"
    "          } catch {}\n"
    "        }\n"
    "      }",

    "      let soapGenerated = false;\n"
    "      while (true) {\n"
    "        const { done, value } = await reader.read();\n"
    "        if (done) break;\n"
    "        sseBuffer += decoder.decode(value, { stream: true });\n"
    "        const lines = sseBuffer.split('\\n');\n"
    "        sseBuffer = lines.pop() || '';\n"
    "        for (const line of lines) {\n"
    "          if (!line.startsWith('data: ')) continue;\n"
    "          const raw = line.slice(6).trim();\n"
    "          if (raw === '[DONE]') {\n"
    "            setStreamStatus('');\n"
    "            // If stream ended and AI never produced valid SOAP JSON\n"
    "            // (e.g. AI returned plain-text refusal for borderline input)\n"
    "            if (!soapGenerated) {\n"
    "              setError('⚠ Could not generate a SOAP note from this transcript. '\n"
    "                + 'Please provide a more complete clinical encounter description.');\n"
    "            }\n"
    "            break;\n"
    "          }\n"
    "          try {\n"
    "            const evt = JSON.parse(raw);\n"
    "            if (evt.type === 'tool_result') {\n"
    "              setStreamStatus('Retrieved patient history…');\n"
    "              accumulated = '';\n"
    "            } else if (evt.type === 'text') {\n"
    "              accumulated += evt.text;\n"
    "              const partial = extractPartialFields(accumulated);\n"
    "              if (Object.keys(partial).length > 0) setNote(prev => ({ ...prev, ...partial }));\n"
    "              const j0 = accumulated.indexOf('{'), j1 = accumulated.lastIndexOf('}');\n"
    "              if (j0 !== -1 && j1 > j0) {\n"
    "                try {\n"
    "                  const parsed = JSON.parse(accumulated.slice(j0, j1 + 1));\n"
    "                  if (parsed.subjective !== undefined) {\n"
    "                    setNote(parsed); saveDraft(parsed);\n"
    "                    soapGenerated = true;\n"
    "                  }\n"
    "                } catch {}\n"
    "              }\n"
    "            } else if (evt.type === 'insufficient') {\n"
    "              // Backend detected insufficient clinical content before calling AI\n"
    "              setNote(evt.note || {});\n"
    "              setError('⚠ Not enough clinical content to generate a SOAP note. '\n"
    "                + 'Please include patient symptoms, history, and clinical findings.');\n"
    "              soapGenerated = true; // prevent double-error on [DONE]\n"
    "            } else if (evt.type === 'content') {\n"
    "              // Legacy fallback\n"
    "              try { const p = JSON.parse(evt.text); setNote(p); soapGenerated = true; } catch {}\n"
    "            }\n"
    "          } catch {}\n"
    "        }\n"
    "      }",
    'SSE loop: insufficient handling + soapGenerated flag'
)

with open(ws_path, 'w') as f:
    f.write(ws)

print(f'Frontend: {changes_fe} changes applied.')
