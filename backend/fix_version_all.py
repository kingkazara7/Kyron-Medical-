#!/usr/bin/env python3
"""
Fix three version-related issues:
1. Backend: store _transcript in NoteVersion.content so each version is self-contained
2. Frontend: version click handler restores that version's transcript
3. Frontend: version label bar always visible (read-only shows saved label, edit shows input)
4. Frontend: initial load prefers version's own _transcript over encounter.raw_input
"""

# ─── Backend fix ─────────────────────────────────────────────────────────────
be_path = '/home/ubuntu/scribe/backend/routers/encounters.py'
with open(be_path) as f:
    be = f.read()

old_be = (
    '    # Build content dict; optionally embed the version label as __label\n'
    '    content_dict = req.content.model_dump()\n'
    '    if req.label:'
)
new_be = (
    '    # Build content dict; optionally embed the version label as __label\n'
    '    content_dict = req.content.model_dump()\n'
    '    # Snapshot the transcript so each version is fully self-contained\n'
    '    if req.raw_input:\n'
    "        content_dict['_transcript'] = req.raw_input\n"
    '    if req.label:'
)

if old_be in be:
    be = be.replace(old_be, new_be, 1)
    print('Backend: transcript snapshot into version content OK')
else:
    print('WARN: backend pattern not found')

with open(be_path, 'w') as f:
    f.write(be)

# ─── Frontend fixes ───────────────────────────────────────────────────────────
ws_path = '/home/ubuntu/scribe/frontend/src/pages/Workspace.jsx'
with open(ws_path) as f:
    ws = f.read()

changes = 0

def rep(old, new, label):
    global ws, changes
    if old in ws:
        ws = ws.replace(old, new, 1)
        changes += 1
        print(f'Frontend {label}: OK')
    else:
        print(f'WARN: {label} pattern not found')

# ── Fix 1: Initial load — lift _transcript out of inner block so it falls back
# to version's own transcript before encounter.raw_input
rep(
    '      // Load saved versions first (baseline)\n'
    '      // If a specific version was requested via navigation state, open it directly\n'
    '      const requestedVersionNo = location.state?.viewVersion ?? null;\n'
    '      if (data.versions?.length) {\n'
    '        const requestedVer = requestedVersionNo\n'
    '          ? data.versions.find(v => v.version_no === requestedVersionNo)\n'
    '          : null;\n'
    '        const targetVer = requestedVer ?? data.versions[data.versions.length - 1];\n'
    '        const { __label, _transcript, ...noteContent } = targetVer.content;\n'
    '        setNote(noteContent);\n'
    '        setCurrentVersion(targetVer.version_no);\n'
    '      }\n'
    '\n'
    '      // Restore transcript from encounter.raw_input (last generate/save)\n'
    '      const restoredTranscript = data.raw_input || \'\';\n'
    '      setTranscript(restoredTranscript);\n'
    '      transcriptRef.current = restoredTranscript;',

    '      // Load saved versions first (baseline)\n'
    '      // If a specific version was requested via navigation state, open it directly\n'
    '      const requestedVersionNo = location.state?.viewVersion ?? null;\n'
    '      let versionTranscript;\n'
    '      if (data.versions?.length) {\n'
    '        const requestedVer = requestedVersionNo\n'
    '          ? data.versions.find(v => v.version_no === requestedVersionNo)\n'
    '          : null;\n'
    '        const targetVer = requestedVer ?? data.versions[data.versions.length - 1];\n'
    '        const { __label, _transcript, ...noteContent } = targetVer.content;\n'
    '        setNote(noteContent);\n'
    '        setCurrentVersion(targetVer.version_no);\n'
    '        versionTranscript = _transcript;\n'
    '      }\n'
    '\n'
    '      // Restore transcript: prefer version\'s own snapshot, fall back to encounter.raw_input\n'
    '      const restoredTranscript = versionTranscript ?? data.raw_input ?? \'\';\n'
    '      setTranscript(restoredTranscript);\n'
    '      transcriptRef.current = restoredTranscript;',
    'initial load transcript'
)

# ── Fix 2: Version click handler — also restore _transcript
rep(
    '                    onClick={() => {\n'
    '                      const { __label, ...noteContent } = v.content;\n'
    '                      setNote(noteContent);\n'
    '                      setViewingVersion(v.version_no);\n'
    '                      api.post(`/encounters/${id}/view-version/${v.version_no}`).catch(() => {});\n'
    '                    }}',

    '                    onClick={() => {\n'
    '                      const { __label, _transcript, ...noteContent } = v.content;\n'
    '                      setNote(noteContent);\n'
    '                      if (_transcript !== undefined) {\n'
    '                        setTranscript(_transcript);\n'
    '                        transcriptRef.current = _transcript;\n'
    '                      }\n'
    '                      setViewingVersion(v.version_no);\n'
    '                      api.post(`/encounters/${id}/view-version/${v.version_no}`).catch(() => {});\n'
    '                    }}',
    'version click transcript restore'
)

# ── Fix 3: Version label bar — always visible (read-only shows label text, edit shows input)
rep(
    '        {/* ── Version label input (only when editable) ── */}\n'
    '        {!isReadOnly && (\n'
    '          <div className="border-b border-clinical-border bg-clinical-surface/50 px-5 py-2 flex items-center gap-3">\n'
    '            <label className="text-xs text-clinical-muted whitespace-nowrap shrink-0">Version label</label>\n'
    '            <input\n'
    '              className="flex-1 bg-clinical-bg border border-clinical-border rounded px-3 py-1.5 text-xs text-clinical-text focus:outline-none focus:border-clinical-accent/50 transition-colors"\n'
    '              placeholder="Optional · max 4 words (e.g. initial assessment review)"\n'
    '              value={versionLabel}\n'
    '              onChange={e => handleLabelChange(e.target.value)}\n'
    '              maxLength={60}\n'
    '            />\n'
    '            <span className={`text-xs shrink-0 tabular-nums ${wordCount >= 4 ? \'text-clinical-warning\' : \'text-clinical-muted\'}`}>\n'
    '              {wordCount}/4\n'
    '            </span>\n'
    '          </div>\n'
    '        )}',

    '        {/* ── Version label — always visible above transcript ── */}\n'
    '        <div className="border-b border-clinical-border bg-clinical-surface/50 px-5 py-2 flex items-center gap-3">\n'
    '          <label className="text-xs text-clinical-muted whitespace-nowrap shrink-0">Version label</label>\n'
    '          {isReadOnly ? (\n'
    '            <span className="text-xs text-clinical-accent italic">\n'
    '              {versions.find(v => v.version_no === viewingVersion)?.content?.__label\n'
    '                || <span className="text-clinical-muted italic">—</span>}\n'
    '            </span>\n'
    '          ) : (\n'
    '            <>\n'
    '              <input\n'
    '                className="flex-1 bg-clinical-bg border border-clinical-border rounded px-3 py-1.5 text-xs text-clinical-text focus:outline-none focus:border-clinical-accent/50 transition-colors"\n'
    '                placeholder="Optional · max 4 words (e.g. initial assessment)"\n'
    '                value={versionLabel}\n'
    '                onChange={e => handleLabelChange(e.target.value)}\n'
    '                maxLength={60}\n'
    '              />\n'
    '              <span className={`text-xs shrink-0 tabular-nums ${wordCount >= 4 ? \'text-clinical-warning\' : \'text-clinical-muted\'}`}>\n'
    '                {wordCount}/4\n'
    '              </span>\n'
    '            </>\n'
    '          )}\n'
    '        </div>',
    'version label bar always visible'
)

with open(ws_path, 'w') as f:
    f.write(ws)

print(f'\nDone: {changes}/3 frontend changes applied.')
