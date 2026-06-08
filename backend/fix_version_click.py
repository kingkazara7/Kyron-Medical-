#!/usr/bin/env python3
"""
Fix: version click handler — when _transcript is missing (old versions),
clear the transcript with a placeholder note rather than silently keeping the
current content, so the user knows this version has no transcript snapshot.
"""
path = '/home/ubuntu/scribe/frontend/src/pages/Workspace.jsx'
with open(path) as f:
    c = f.read()

old = (
    '                    onClick={() => {\n'
    '                      const { __label, _transcript, ...noteContent } = v.content;\n'
    '                      setNote(noteContent);\n'
    '                      if (_transcript !== undefined) {\n'
    '                        setTranscript(_transcript);\n'
    '                        transcriptRef.current = _transcript;\n'
    '                      }\n'
    '                      setViewingVersion(v.version_no);\n'
    '                      api.post(`/encounters/${id}/view-version/${v.version_no}`).catch(() => {});\n'
    '                    }}'
)

new = (
    '                    onClick={() => {\n'
    '                      const { __label, _transcript, ...noteContent } = v.content;\n'
    '                      setNote(noteContent);\n'
    '                      // Restore this version\'s transcript snapshot if available\n'
    '                      const tx = _transcript ?? \'[Transcript not captured for this version]\';\n'
    '                      setTranscript(tx);\n'
    '                      transcriptRef.current = tx;\n'
    '                      setViewingVersion(v.version_no);\n'
    '                      api.post(`/encounters/${id}/view-version/${v.version_no}`).catch(() => {});\n'
    '                    }}'
)

if old in c:
    c = c.replace(old, new, 1)
    print('OK: version click transcript fallback patched')
else:
    print('WARN: pattern not found')

with open(path, 'w') as f:
    f.write(c)
