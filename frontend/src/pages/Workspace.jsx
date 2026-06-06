import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import api from '../api';

function ICD10Search({ onAppend }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const timer = useRef(null);

  useEffect(() => {
    if (!query.trim() || query.length < 2) { setResults([]); return; }
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      setLoading(true);
      try {
        const { data } = await api.get('/icd10/search', { params: { q: query } });
        setResults(data.results);
      } catch {} finally { setLoading(false); }
    }, 400);
  }, [query]);

  return (
    <div className="card p-3">
      <div className="text-xs font-semibold text-clinical-text-dim uppercase tracking-wider mb-2">ICD-10 Search</div>
      <input
        className="input mb-2"
        placeholder="Search symptom or condition…"
        value={query}
        onChange={e => setQuery(e.target.value)}
      />
      {loading && <div className="text-xs text-clinical-muted">Searching…</div>}
      <div className="space-y-1 max-h-48 overflow-y-auto">
        {results.map(r => (
          <button
            key={r.code}
            onClick={() => { onAppend(r); setQuery(''); setResults([]); }}
            className="w-full text-left px-2 py-1.5 rounded hover:bg-clinical-border text-xs transition-colors"
          >
            <span className="font-mono text-clinical-accent mr-2">{r.code}</span>
            <span className="text-clinical-text-dim">{r.description}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function VersionHistory({ versions, currentVersion }) {
  const [expanded, setExpanded] = useState(false);
  if (!versions || versions.length <= 1) return null;

  return (
    <div className="card p-3">
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center justify-between text-xs font-semibold text-clinical-text-dim uppercase tracking-wider"
      >
        <span>Version History ({versions.length})</span>
        <span>{expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && (
        <div className="mt-2 space-y-1">
          {[...versions].reverse().map(v => (
            <div key={v.version_no} className={`px-2 py-1.5 rounded text-xs flex items-center justify-between ${v.version_no === currentVersion ? 'bg-clinical-accent/10 border border-clinical-accent/30' : 'hover:bg-clinical-border'}`}>
              <span className="font-mono text-clinical-text-dim">v{v.version_no}</span>
              <span className="text-clinical-muted">{new Date(v.saved_at).toLocaleString()}</span>
              {v.version_no === currentVersion && <span className="tag bg-clinical-accent/10 text-clinical-accent">current</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DiffView({ versions }) {
  const [v1, setV1] = useState('');
  const [v2, setV2] = useState('');

  if (!versions || versions.length < 2) return null;

  const ver1 = versions.find(v => v.version_no === parseInt(v1));
  const ver2 = versions.find(v => v.version_no === parseInt(v2));

  const diffText = (a, b) => {
    if (!a || !b) return null;
    const aLines = a.split('\n');
    const bLines = b.split('\n');
    return { added: bLines.filter(l => !aLines.includes(l)), removed: aLines.filter(l => !bLines.includes(l)) };
  };

  const sections = ['subjective', 'objective', 'assessment', 'plan'];

  return (
    <div className="card p-3 mt-3">
      <div className="text-xs font-semibold text-clinical-text-dim uppercase tracking-wider mb-2">Version Diff</div>
      <div className="flex gap-2 mb-3">
        <select className="input flex-1 text-xs" value={v1} onChange={e => setV1(e.target.value)}>
          <option value="">From version…</option>
          {versions.map(v => <option key={v.version_no} value={v.version_no}>v{v.version_no}</option>)}
        </select>
        <select className="input flex-1 text-xs" value={v2} onChange={e => setV2(e.target.value)}>
          <option value="">To version…</option>
          {versions.map(v => <option key={v.version_no} value={v.version_no}>v{v.version_no}</option>)}
        </select>
      </div>
      {ver1 && ver2 && sections.map(sec => {
        const diff = diffText(ver1.content[sec] || '', ver2.content[sec] || '');
        if (!diff || (!diff.added.length && !diff.removed.length)) return null;
        return (
          <div key={sec} className="mb-3">
            <div className="soap-label">{sec}</div>
            {diff.removed.map((l, i) => l.trim() && (
              <div key={i} className="text-xs bg-clinical-danger/10 text-clinical-danger px-2 py-0.5 rounded mb-0.5 font-mono">− {l}</div>
            ))}
            {diff.added.map((l, i) => l.trim() && (
              <div key={i} className="text-xs bg-clinical-success/10 text-clinical-success px-2 py-0.5 rounded mb-0.5 font-mono">+ {l}</div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

export default function Workspace() {
  const { id } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();

  const [encounter, setEncounter] = useState(null);
  const [transcript, setTranscript] = useState('');
  const [note, setNote] = useState({ subjective: '', objective: '', assessment: '', plan: '', icd10_codes: [] });
  const [streaming, setStreaming] = useState(false);
  const [streamStatus, setStreamStatus] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [versions, setVersions] = useState([]);
  const [currentVersion, setCurrentVersion] = useState(null);
  const [showDiff, setShowDiff] = useState(false);
  const draftTimer = useRef(null);
  const abortRef = useRef(null);

  // Load encounter
  useEffect(() => {
    api.get(`/encounters/${id}`).then(({ data }) => {
      setEncounter(data);
      setTranscript(data.raw_input || '');
      setVersions(data.versions || []);
      if (data.versions?.length) {
        const latest = data.versions[data.versions.length - 1];
        setNote(latest.content);
        setCurrentVersion(latest.version_no);
      }
      // Restore draft if no saved note
      if (data.draft && !data.versions?.length) {
        setNote(data.draft);
      } else if (data.draft) {
        setNote(data.draft);
      }
    }).catch(() => navigate('/'));
  }, [id]);

  // Auto-save draft
  const saveDraft = useCallback((noteData) => {
    clearTimeout(draftTimer.current);
    draftTimer.current = setTimeout(() => {
      api.put('/drafts', { encounter_id: parseInt(id), content: noteData }).catch(() => {});
    }, 2000);
  }, [id]);

  const updateNoteField = (field, value) => {
    const updated = { ...note, [field]: value };
    setNote(updated);
    saveDraft(updated);
  };

  const handleGenerate = async () => {
    if (!transcript.trim()) { setError('Please enter a transcript or observations.'); return; }
    setError('');
    setStreaming(true);
    setStreamStatus('Connecting…');
    setNote({ subjective: '', objective: '', assessment: '', plan: '', icd10_codes: [] });
    abortRef.current = new AbortController();

    try {
      const token = localStorage.getItem('token');
      const res = await fetch(`/api/encounters/generate`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          encounter_id: parseInt(id),
          transcript,
          template_id: encounter?.template_id,
        }),
        signal: abortRef.current.signal,
      });

      if (!res.ok) { throw new Error('Generation failed'); }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = '';
      setStreamStatus('Generating…');

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (raw === '[DONE]') { setStreamStatus(''); break; }
          try {
            const evt = JSON.parse(raw);
            if (evt.type === 'tool_result') {
              setStreamStatus('Retrieved patient history…');
            } else if (evt.type === 'text') {
              accumulated += evt.text;
              // Try to parse accumulated JSON
              try {
                const parsed = JSON.parse(accumulated);
                if (parsed.subjective !== undefined) {
                  setNote(parsed);
                  saveDraft(parsed);
                }
              } catch {}
            } else if (evt.type === 'content') {
              // Full JSON in one shot (insufficient content case)
              try {
                const parsed = JSON.parse(evt.text);
                setNote(parsed);
              } catch {}
            }
          } catch {}
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') setError('Generation failed. Please try again.');
    } finally {
      setStreaming(false);
      setStreamStatus('');
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      const { data } = await api.post('/encounters/save', {
        encounter_id: parseInt(id),
        content: note,
        raw_input: transcript,
      });
      setSaved(true);
      setCurrentVersion(data.version_no);
      // Refresh versions
      const { data: enc } = await api.get(`/encounters/${id}`);
      setVersions(enc.versions || []);
      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Session expired. Your note has been auto-saved as a draft. Please log in again.');
      } else {
        setError('Save failed. Your draft is preserved.');
      }
    } finally {
      setSaving(false);
    }
  };

  const appendICD10 = (code) => {
    const codes = note.icd10_codes || [];
    if (codes.find(c => c.code === code.code)) return;
    const updated = { ...note, icd10_codes: [...codes, { code: code.code, description: code.description }] };
    setNote(updated);
    saveDraft(updated);
  };

  const removeICD10 = (code) => {
    const updated = { ...note, icd10_codes: (note.icd10_codes || []).filter(c => c.code !== code) };
    setNote(updated);
    saveDraft(updated);
  };

  if (!encounter) return (
    <div className="min-h-screen bg-clinical-bg flex items-center justify-center text-clinical-muted text-sm">Loading encounter…</div>
  );

  return (
    <div className="h-screen bg-clinical-bg flex flex-col overflow-hidden">
      {/* Header */}
      <header className="border-b border-clinical-border bg-clinical-surface px-4 py-2.5 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate('/')} className="text-clinical-muted hover:text-clinical-text text-sm">← Back</button>
          <div className="text-sm font-medium">{encounter.patient?.first_name} {encounter.patient?.last_name}</div>
          <div className="text-xs text-clinical-muted">DOB: {encounter.patient?.dob}</div>
          {encounter.template_name && (
            <span className="tag bg-clinical-accent/10 text-clinical-accent text-xs">{encounter.template_name}</span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {currentVersion && <span className="text-xs text-clinical-muted">v{currentVersion}</span>}
          <span className={`tag text-xs ${encounter.status === 'saved' ? 'bg-clinical-success/10 text-clinical-success' : 'bg-clinical-warning/10 text-clinical-warning'}`}>
            {encounter.status}
          </span>
          <button onClick={handleSave} disabled={saving || streaming} className="btn-primary text-xs py-1.5">
            {saving ? 'Saving…' : saved ? '✓ Saved' : 'Save Note'}
          </button>
        </div>
      </header>

      {error && (
        <div className="bg-clinical-danger/10 border-b border-clinical-danger/20 px-4 py-2 text-sm text-clinical-danger">
          {error}
          <button onClick={() => setError('')} className="ml-3 text-clinical-danger/60 hover:text-clinical-danger">✕</button>
        </div>
      )}

      {/* Main layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Input */}
        <div className="w-80 shrink-0 border-r border-clinical-border flex flex-col overflow-hidden">
          <div className="p-3 border-b border-clinical-border shrink-0">
            <div className="label">Transcript / Observations</div>
            <textarea
              className="input resize-none text-xs font-mono"
              rows={10}
              value={transcript}
              onChange={e => setTranscript(e.target.value)}
              placeholder="Paste encounter transcript or type clinical observations…"
            />
          </div>
          <div className="p-3 space-y-2 overflow-y-auto flex-1">
            <button
              onClick={handleGenerate}
              disabled={streaming || !transcript.trim()}
              className="btn-primary w-full flex items-center justify-center gap-2"
            >
              {streaming ? (
                <>
                  <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  {streamStatus || 'Generating…'}
                </>
              ) : (
                <>
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  Generate Note
                </>
              )}
            </button>
            <ICD10Search onAppend={appendICD10} />
            <VersionHistory versions={versions} currentVersion={currentVersion} />
            {versions.length >= 2 && (
              <button onClick={() => setShowDiff(v => !v)} className="btn-ghost w-full text-xs">
                {showDiff ? 'Hide' : 'Show'} Version Diff
              </button>
            )}
            {showDiff && <DiffView versions={versions} />}
          </div>
        </div>

        {/* Right: SOAP note */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {/* Subjective */}
          <div className="soap-section">
            <div className="soap-label">S — Subjective</div>
            <textarea
              className="w-full bg-transparent text-sm text-clinical-text resize-none focus:outline-none min-h-[80px]"
              value={note.subjective}
              onChange={e => updateNoteField('subjective', e.target.value)}
              placeholder={streaming ? '' : 'Chief complaint, HPI, ROS…'}
            />
            {streaming && !note.subjective && <span className="text-clinical-muted text-xs sse-cursor">Generating</span>}
          </div>

          {/* Objective */}
          <div className="soap-section">
            <div className="soap-label">O — Objective</div>
            <textarea
              className="w-full bg-transparent text-sm text-clinical-text resize-none focus:outline-none min-h-[80px]"
              value={note.objective}
              onChange={e => updateNoteField('objective', e.target.value)}
              placeholder={streaming ? '' : 'Vital signs, physical exam, diagnostic results…'}
            />
            {streaming && !note.objective && note.subjective && <span className="text-clinical-muted text-xs sse-cursor">Generating</span>}
          </div>

          {/* Assessment */}
          <div className="soap-section">
            <div className="soap-label">A — Assessment</div>
            <textarea
              className="w-full bg-transparent text-sm text-clinical-text resize-none focus:outline-none min-h-[80px]"
              value={note.assessment}
              onChange={e => updateNoteField('assessment', e.target.value)}
              placeholder={streaming ? '' : 'Clinical impression, differential…'}
            />
            {streaming && !note.assessment && note.objective && <span className="text-clinical-muted text-xs sse-cursor">Generating</span>}

            {/* ICD-10 codes */}
            {(note.icd10_codes?.length > 0) && (
              <div className="mt-2 pt-2 border-t border-clinical-border">
                <div className="text-xs text-clinical-text-dim mb-1.5">ICD-10 Codes</div>
                <div className="flex flex-wrap gap-1.5">
                  {note.icd10_codes.map(c => (
                    <span key={c.code} className="tag bg-clinical-accent/10 text-clinical-accent border border-clinical-accent/20 group cursor-default">
                      <span className="font-mono mr-1">{c.code}</span>
                      <span className="text-clinical-accent/70 mr-1">{c.description}</span>
                      <button onClick={() => removeICD10(c.code)} className="opacity-0 group-hover:opacity-100 text-clinical-danger hover:text-clinical-danger ml-1">✕</button>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Plan */}
          <div className="soap-section">
            <div className="soap-label">P — Plan</div>
            <textarea
              className="w-full bg-transparent text-sm text-clinical-text resize-none focus:outline-none min-h-[100px]"
              value={note.plan}
              onChange={e => updateNoteField('plan', e.target.value)}
              placeholder={streaming ? '' : 'Treatment plan, medications, referrals, follow-up…'}
            />
            {streaming && !note.plan && note.assessment && <span className="text-clinical-muted text-xs sse-cursor">Generating</span>}
          </div>
        </div>
      </div>
    </div>
  );
}
