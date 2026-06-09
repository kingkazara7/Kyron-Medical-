import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import api from '../api';

// ── Eastern-time formatter ────────────────────────────────────────────────
function fmtET(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-US', {
    timeZone: 'America/New_York',
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

// ── ICD-10 live search ─────────────────────────────────────────────────────
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
    <div>
      <div className="text-xs font-semibold text-clinical-text-dim uppercase tracking-wider mb-2">ICD-10 Search</div>
      <input
        className="input mb-2 text-xs"
        placeholder="Search symptom or condition…"
        value={query}
        onChange={e => setQuery(e.target.value)}
      />
      {loading && <div className="text-xs text-clinical-muted">Searching…</div>}
      <div className="space-y-1 max-h-36 overflow-y-auto">
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

// ── Version history panel (draft-only sidebar) ─────────────────────────────
function VersionHistory({ versions, currentVersion, onLoadVersion, defaultExpanded = false }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  if (!versions || versions.length < 1) return null;

  return (
    <div>
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center justify-between text-xs font-semibold text-clinical-text-dim uppercase tracking-wider mb-1"
      >
        <span>Version History ({versions.length})</span>
        <span>{expanded ? '▲' : '▼'}</span>
      </button>
      {expanded && (
        <div className="mt-2 space-y-1 max-h-48 overflow-y-auto">
          {[...versions].map(v => {
            const isCurrent = v.version_no === currentVersion;
            const label = v.content?.__label;
            return (
              <button
                key={v.version_no}
                onClick={() => onLoadVersion(v)}
                disabled={isCurrent}
                className={`w-full text-left px-2 py-2 rounded text-xs transition-colors ${isCurrent ? 'bg-clinical-accent/10 border border-clinical-accent/30 cursor-default' : 'hover:bg-clinical-border cursor-pointer'}`}
              >
                <div className="flex items-center justify-between mb-0.5">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono font-semibold text-clinical-text">v{v.version_no}</span>
                    {label && <span className="text-clinical-text-dim italic">"{label}"</span>}
                  </div>
                  {isCurrent
                    ? <span className="tag bg-clinical-accent/10 text-clinical-accent">current</span>
                    : <span className="tag bg-clinical-surface border border-clinical-border text-clinical-text-dim">Load</span>
                  }
                </div>
                <div className="text-clinical-muted leading-tight">
                  <span className="text-clinical-text-dim">{v.saved_by_name || 'Unknown'}</span>
                  <span className="mx-1">·</span>
                  <span>{fmtET(v.saved_at)}</span>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Version diff panel ─────────────────────────────────────────────────────
function DiffView({ versions }) {
  const [v1, setV1] = useState('');
  const [v2, setV2] = useState('');
  if (!versions || versions.length < 2) return null;

  const ver1 = versions.find(v => v.version_no === parseInt(v1));
  const ver2 = versions.find(v => v.version_no === parseInt(v2));
  const sections = ['subjective', 'objective', 'assessment', 'plan'];

  const diffText = (a, b) => {
    if (!a || !b) return null;
    const aLines = a.split('\n');
    const bLines = b.split('\n');
    return { added: bLines.filter(l => !aLines.includes(l)), removed: aLines.filter(l => !bLines.includes(l)) };
  };

  return (
    <div className="mt-3 pt-3 border-t border-clinical-border">
      <div className="text-xs font-semibold text-clinical-text-dim uppercase tracking-wider mb-2">Version Diff</div>
      <div className="flex gap-2 mb-3">
        <select className="input flex-1 text-xs" value={v1} onChange={e => setV1(e.target.value)}>
          <option value="">From…</option>
          {versions.map(v => <option key={v.version_no} value={v.version_no}>v{v.version_no}</option>)}
        </select>
        <select className="input flex-1 text-xs" value={v2} onChange={e => setV2(e.target.value)}>
          <option value="">To…</option>
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

// ── Collapsible SOAP section ───────────────────────────────────────────────
const SOAP_LABELS = {
  subjective: 'S — Subjective',
  objective:  'O — Objective',
  assessment: 'A — Assessment',
  plan:       'P — Plan',
};
const SOAP_PLACEHOLDERS = {
  subjective: 'Chief complaint, HPI, ROS…',
  objective:  'Vital signs, physical exam, diagnostic results…',
  assessment: 'Clinical impression, differential…',
  plan:       'Treatment plan, medications, referrals, follow-up…',
};

function SOAPSection({ field, value, onChange, streaming, prevFilled, readOnly, children }) {
  const [open, setOpen] = useState(true);
  const taRef = useRef(null);

  // Auto-resize textarea whenever content or open state changes
  useEffect(() => {
    if (!taRef.current || !open) return;
    taRef.current.style.height = 'auto';
    taRef.current.style.height = taRef.current.scrollHeight + 'px';
  }, [value, open]);

  return (
    <div className="border border-clinical-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-4 py-2.5 bg-clinical-surface hover:bg-clinical-border/20 transition-colors"
      >
        <span className="text-xs font-semibold text-clinical-text-dim uppercase tracking-wider">{SOAP_LABELS[field]}</span>
        <span className="text-xs text-clinical-muted">{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div className="px-4 py-3 bg-clinical-bg">
          <textarea
            ref={taRef}
            className="w-full bg-transparent text-sm font-mono text-clinical-text resize-none focus:outline-none leading-relaxed overflow-hidden"
            style={{ minHeight: '80px' }}
            value={value}
            onChange={e => {
              if (readOnly) return;
              onChange(e.target.value);
              // Inline resize on every keystroke for instant feedback
              e.target.style.height = 'auto';
              e.target.style.height = e.target.scrollHeight + 'px';
            }}
            placeholder={streaming ? '' : SOAP_PLACEHOLDERS[field]}
            readOnly={readOnly}
          />
          {streaming && !value && prevFilled && (
            <span className="text-clinical-muted text-xs sse-cursor">Generating</span>
          )}
          {children}
        </div>
      )}
    </div>
  );
}

// ── Word-limit helper (max 4 words) ───────────────────────────────────────
function limitToWords(val, max) {
  const words = val.trim().split(/\s+/).filter(w => w.length > 0);
  return words.slice(0, max).join(' ');
}

// ── Main workspace ─────────────────────────────────────────────────────────
export default function Workspace() {
  const { id } = useParams();
  const { user, logout } = useAuth();
  const isAdmin = user?.role === 'admin';
  const navigate = useNavigate();
  const location = useLocation();

  const [encounter, setEncounter]           = useState(null);
  const [transcript, setTranscript]         = useState('');
  const [note, setNote]                     = useState({ subjective: '', objective: '', assessment: '', plan: '', icd10_codes: [] });

  // Mirror of backend has_clinical_content() — validates transcript clinical quality
  const hasClinicalContent = (text) => {
    const lower = text.toLowerCase();
    const words = lower.split(/\s+/).filter(w => w.length > 0);
    if (words.length < 10) return false;
    const CLINICAL_KW = [
      'pain', 'ache', 'fever', 'cough', 'nausea', 'vomit', 'bleed', 'dyspnea',
      'breath', 'chest', 'abdomen', 'head', 'dizziness', 'fatigue', 'swollen',
      'rash', 'history', 'medication', 'diagnosis', 'complaint', 'symptom',
      'patient', 'exam', 'bp', 'pulse', 'temp', 'hr ', 'rr ', 'o2', 'spo2',
      'heart', 'lung', 'edema', 'hypertension', 'diabetes', 'asthma', 'copd',
      'follow', 'visit', 'treatment', 'prescribed', 'imaging', 'lab', 'x-ray',
      'mri', 'ct ', 'ekg', 'ecg', 'blood', 'urine', 'infection', 'fracture',
      'laceration', 'sprain', 'strain', 'allergy', 'review', 'presenting',
    ];
    const ANCHOR = [
      'patient', 'presenting', 'complaint', 'history', 'diagnosis',
      'exam', 'visit', 'follow', 'assessment', 'treatment', 'encounter',
    ];
    const kwMatches = CLINICAL_KW.filter(kw => lower.includes(kw)).length;
    if (kwMatches < 3) return false;
    return ANCHOR.some(a => lower.includes(a));
  };

  // Validates input for garbage content — used for both transcript and SOAP fields.
  // Detects two patterns:
  //   1. A standalone digit sequence of 5+ consecutive chars (e.g. "1231232")
  //   2. Four or more consecutive whitespace-separated pure-digit tokens
  //      (e.g. "123 123 1231 123" — spaced-out number spam)
  // Legitimate medical values (BP 148/90, HbA1c 7.8%, 250mg) are not affected
  // because they contain slashes, decimals, letters, or % signs.
  const hasNoGarbageInput = (text) => {
    if (!text || !text.trim()) return true;         // empty fields are allowed
    if (!/[a-zA-Z]{2,}/.test(text)) return false;  // must contain real words

    // Pattern 1: standalone long digit run (e.g. "1231232")
    if (/(?<![a-zA-Z\d./])\d{5,}(?![a-zA-Z\d./])/.test(text)) return false;

    // Pattern 2: 4+ consecutive space-separated pure-digit tokens (e.g. "123 456 789 012")
    const tokens = text.trim().split(/\s+/);
    let run = 0;
    for (const tok of tokens) {
      if (/^\d+$/.test(tok)) {
        run++;
        if (run >= 4) return false;
      } else {
        run = 0;
      }
    }

    return true;
  };

  const [versionLabel, setVersionLabel]     = useState('');
  const [streaming, setStreaming]           = useState(false);
  const [streamStatus, setStreamStatus]     = useState('');
  const [saving, setSaving]                 = useState(false);
  const [saved, setSaved]                   = useState(false);
  const [error, setError]                   = useState('');
  const [deactivated, setDeactivated]            = useState(false);
  const [sessionExpired, setSessionExpired]      = useState(false);
  const [sessionSuperseded, setSessionSuperseded] = useState(false);
  const [templates, setTemplates]            = useState([]);
  const [activeTemplateId, setActiveTemplateId] = useState(null);
  const [templatePickerOpen, setTemplatePickerOpen] = useState(false);
  const templatePickerRef = useRef(null);
  const [versions, setVersions]             = useState([]);
  const [currentVersion, setCurrentVersion] = useState(null);
  const [viewingVersion, setViewingVersion] = useState(null);
  const [showDiff, setShowDiff]             = useState(false);
  const [isReadOnly, setIsReadOnly]         = useState(false);
  // Real-time AI content validation
  const [aiContentValid, setAiContentValid] = useState(true);
  const [aiValidating, setAiValidating]     = useState(false);
  const aiValidateTimer                     = useRef(null);


  // Invalid when: SOAP has INSUFFICIENT_RESPONSE markers, OR (while editing) transcript is not clinical
  const hasNoteIssue = (() => {
    const s = note.subjective || '';
    const a = note.assessment || '';
    const pl = note.plan || '';
    const o = note.objective || '';

    // 1. SOAP contains AI insufficient-response markers — blocks in ANY mode
    if (
      s.includes('Insufficient clinical content') ||
      o.includes('No objective findings documented') ||
      a.includes('Unable to generate assessment') ||
      pl.includes('complete clinical transcript')
    ) return true;

    if (!isReadOnly) {
      // 2. Instant heuristic — numeric/pattern garbage in any SOAP field
      if ([s, o, a, pl].some(f => f.trim() && !hasNoGarbageInput(f))) return true;
      // 3. Instant heuristic — numeric/pattern garbage in the transcript
      if (transcript.trim() && !hasNoGarbageInput(transcript)) return true;
      // 4. Real-time AI verdict — catches gibberish words the heuristic misses.
      //    This is now reachable (previously dead code after the transcript return).
      if (!aiContentValid) return true;
      // NOTE: no hasClinicalContent() gate while editing — a valid transcript on
      //       its own is enough to save (SOAP optional). The AI verdict decides
      //       validity, so short-but-legitimate notes are no longer blocked.
    } else {
      // Read-only saved note: surface the warning badge when a stored transcript
      // is clearly non-clinical (no AI call needed for historical records).
      if (transcript.trim() && !hasClinicalContent(transcript)) return true;
    }
    return false;
  })();
  const [isDirty, setIsDirty]               = useState(false);
  const [lastEditTime, setLastEditTime]     = useState(null);
  const [versionBannerOpen, setVersionBannerOpen] = useState(true);

  const draftTimer      = useRef(null);
  const abortRef        = useRef(null);
  // Refs — always hold latest values so cleanup/unmount doesn't get stale closures
  const isReadOnlyRef      = useRef(false);
  const noteRef            = useRef({ subjective: '', objective: '', assessment: '', plan: '', icd10_codes: [] });
  const transcriptRef      = useRef('');
  const versionLabelRef    = useRef('');

  useEffect(() => {
    api.get('/admin/templates').then(r => {
      setTemplates((r.data || []).filter(t => t.is_active));
    }).catch(() => {});

    api.get(`/encounters/${id}`).then(({ data }) => {
      setEncounter(data);
      setVersions(data.versions || []);
      setActiveTemplateId(data.template_id ?? null);

      // Load saved versions first (baseline)
      // If a specific version was requested via navigation state, open it directly
      const requestedVersionNo = location.state?.viewVersion ?? null;
      let versionTranscript;
      if (data.versions?.length) {
        const requestedVer = requestedVersionNo
          ? data.versions.find(v => v.version_no === requestedVersionNo)
          : null;
        const targetVer = requestedVer ?? data.versions[data.versions.length - 1];
        const { __label, _transcript, ...noteContent } = targetVer.content;
        setNote(noteContent);
        setCurrentVersion(targetVer.version_no);
        versionTranscript = _transcript;
      }

      // Restore transcript: prefer version's own snapshot, fall back to encounter.raw_input
      const restoredTranscript = versionTranscript ?? data.raw_input ?? '';
      setTranscript(restoredTranscript);
      transcriptRef.current = restoredTranscript;

      // Draft overrides everything — restore full in-progress state
      if (data.draft) {
        const { _transcript: draftTranscript, _label: draftLabel, __label, ...noteContent } = data.draft;
        // Restore transcript
        if (draftTranscript !== undefined) {
          setTranscript(draftTranscript);
          transcriptRef.current = draftTranscript;
        }
        // Restore version label
        if (draftLabel) {
          setVersionLabel(draftLabel);
          versionLabelRef.current = draftLabel;
        }
        // Restore SOAP note
        if (noteContent.subjective !== undefined) {
          setNote(noteContent);
        }
      }

      if (data.status === 'saved') {
        // Unlock if: explicitly navigated for new version, OR draft in progress
        if (location.state?.newVersion || data.draft) {
          setIsReadOnly(false);
        } else {
          setIsReadOnly(true);
          const latestVer = data.versions?.[data.versions.length - 1]?.version_no ?? null;
          setViewingVersion(requestedVersionNo ?? latestVer);
        }
      }
      // Admin: always read-only
      if (isAdmin) {
        setIsReadOnly(true);
        isReadOnlyRef.current = true;
      }
    }).catch(() => navigate('/'));
  }, [id]);

  // Keep refs in sync
  useEffect(() => { isReadOnlyRef.current = isReadOnly; }, [isReadOnly]);
  useEffect(() => { noteRef.current = note; }, [note]);
  useEffect(() => { versionLabelRef.current = versionLabel; }, [versionLabel]);

  // Real-time AI content validation — debounced 1.4 s after user stops typing.
  // Checks transcript + SOAP fields for keyboard-mash / garbage via Claude.
  // Skips validation if read-only or content has not been dirtied yet.
  useEffect(() => {
    if (isReadOnly || !isDirty) { setAiContentValid(true); return; }
    const hasContent = transcript.trim()
      || (note.subjective || '').trim() || (note.objective || '').trim()
      || (note.assessment || '').trim() || (note.plan || '').trim();
    if (!hasContent) { setAiContentValid(true); return; }

    clearTimeout(aiValidateTimer.current);
    setAiValidating(true);
    aiValidateTimer.current = setTimeout(async () => {
      try {
        const { data } = await api.post('/encounters/validate-content', {
          transcript: transcript || '',
          subjective: note.subjective || '',
          objective:  note.objective  || '',
          assessment: note.assessment || '',
          plan:       note.plan       || '',
        });
        setAiContentValid(data.valid);
      } catch { setAiContentValid(true); } // on API error, don't block
      finally   { setAiValidating(false); }
    }, 1400);
    return () => clearTimeout(aiValidateTimer.current);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [transcript, note.subjective, note.objective, note.assessment, note.plan, isReadOnly, isDirty]);

  // Helper: build full draft content (SOAP + transcript + label together)
  const buildDraftContent = useCallback(() => ({
    ...noteRef.current,
    _transcript: transcriptRef.current,
    _label: versionLabelRef.current || undefined,
  }), []);

  // Flush draft via fetch keepalive — works even during browser close/refresh
  const flushDraftKeepAlive = useCallback(() => {
    if (isReadOnlyRef.current) return;
    const token = localStorage.getItem('token');
    fetch('/api/drafts', {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({
        encounter_id: parseInt(id),
        content: buildDraftContent(),
      }),
      keepalive: true,  // survives page close/refresh
    }).catch(() => {});
  }, [id, buildDraftContent]);

  // beforeunload: handles browser refresh (F5) and tab close
  // useEffect cleanup only runs on SPA navigation, NOT on browser refresh
  useEffect(() => {
    window.addEventListener('beforeunload', flushDraftKeepAlive);
    return () => window.removeEventListener('beforeunload', flushDraftKeepAlive);
  }, [flushDraftKeepAlive]);

  // Account deactivation / session events — lock workspace in place
  useEffect(() => {
    const handleDeactivated   = () => setDeactivated(true);
    const handleSessionExpired    = () => setSessionExpired(true);
    const handleSessionSuperseded = () => setSessionSuperseded(true);
    window.addEventListener('kyron:account-deactivated',  handleDeactivated);
    window.addEventListener('kyron:session-expired',      handleSessionExpired);
    window.addEventListener('kyron:session-superseded',   handleSessionSuperseded);
    return () => {
      window.removeEventListener('kyron:account-deactivated',  handleDeactivated);
      window.removeEventListener('kyron:session-expired',      handleSessionExpired);
      window.removeEventListener('kyron:session-superseded',   handleSessionSuperseded);
    };
  }, []);

  // Pre-supersession flush: save draft immediately while token is still valid.
  // The server sends 'flush' 1.5 s before invalidating the session so the save
  // completes and Device B can see the latest content after logging in.
  useEffect(() => {
    const handleFlush = () => flushDraftKeepAlive();
    window.addEventListener('kyron:session-flush', handleFlush);
    return () => window.removeEventListener('kyron:session-flush', handleFlush);
  }, [flushDraftKeepAlive]);

  // Close template picker on outside click
  useEffect(() => {
    if (!templatePickerOpen) return;
    const close = (e) => {
      if (templatePickerRef.current && !templatePickerRef.current.contains(e.target))
        setTemplatePickerOpen(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [templatePickerOpen]);

  // SPA navigation cleanup (Back button, route change within app)
  useEffect(() => {
    return () => {
      clearTimeout(draftTimer.current);
      flushDraftKeepAlive();
    };
  }, [id, flushDraftKeepAlive]);

  // Draft save — immediate, no debounce
  const saveDraft = useCallback((noteData, txOverride, labelOverride) => {
    if (isReadOnlyRef.current) return;
    const label = labelOverride !== undefined ? labelOverride : versionLabelRef.current;
    const content = {
      ...noteData,
      _transcript: txOverride !== undefined ? txOverride : transcriptRef.current,
      ...(label ? { _label: label } : {}),
    };
    api.put('/drafts', { encounter_id: parseInt(id), content }).catch(() => {});
  }, [id]);

  const markEdited = () => { setIsDirty(true); setLastEditTime(new Date()); };

  const updateNoteField = (field, value) => {
    const updated = { ...note, [field]: value };
    setNote(updated);
    saveDraft(updated);
    markEdited();
  };

  const handleLabelChange = (val) => {
    const wordCount = val.trim() === '' ? 0 : val.trim().split(/\s+/).length;
    const clamped = wordCount <= 4 ? val : limitToWords(val, 4);
    setVersionLabel(clamped);
    versionLabelRef.current = clamped;
    // Save label to draft immediately
    saveDraft(noteRef.current, undefined, clamped);
  };

  // ── Template change ───────────────────────────────────────────────────────
  const handleTemplateChange = async (newId) => {
    setActiveTemplateId(newId);
    setTemplatePickerOpen(false);
    api.patch(`/encounters/${id}/template`, { template_id: newId }).catch(() => {});
  };

  // ── SSE generate ──────────────────────────────────────────────────────────
  const handleGenerate = async () => {
    if (!transcript.trim()) { setError('Please enter a transcript or observations.'); return; }
    setError('');
    setStreaming(true);
    setStreamStatus('Connecting…');
    setNote({ subjective: '', objective: '', assessment: '', plan: '', icd10_codes: [] });
    abortRef.current = new AbortController();

    try {
      const token = localStorage.getItem('token');
      const res = await fetch('/api/encounters/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
        body: JSON.stringify({ encounter_id: parseInt(id), transcript, template_id: activeTemplateId }),
        signal: abortRef.current.signal,
      });
      if (res.status === 401) {
        localStorage.removeItem('token'); localStorage.removeItem('user');
        const current = window.location.pathname + window.location.search;
        sessionStorage.setItem('redirectAfterLogin', current);
        // Detect whether session was superseded by another device
        let body = {};
        try { body = await res.clone().json(); } catch { /* ignore */ }
        const isSuperseded = (body.detail || '').includes('superseded');
        const evtName = isSuperseded ? 'kyron:session-superseded' : 'kyron:session-expired';
        window.dispatchEvent(new CustomEvent(evtName));
        setStreaming(false);
        return;
      }
      if (!res.ok) throw new Error('Generation failed');

      const reader  = res.body.getReader();
      const decoder = new TextDecoder();
      let accumulated = '';
      let sseBuffer   = '';
      setStreamStatus('Generating…');

      const extractPartialFields = (text) => {
        const fields = ['subjective', 'objective', 'assessment', 'plan'];
        const partial = {};
        for (const f of fields) {
          const m = text.match(new RegExp('"' + f + '"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)'));
          if (m) {
            partial[f] = m[1]
              .replace(/\\n/g, '\n').replace(/\\t/g, '\t')
              .replace(/\\"/g, '"').replace(/\\\\/g, '\\');
          }
        }
        return partial;
      };

      // Best-effort extraction of the icd10_codes array — works even when the
      // surrounding JSON object hasn't fully closed yet (or a strict parse fails).
      const extractIcdCodes = (text) => {
        const m = text.match(/"icd10_codes"\s*:\s*\[([\s\S]*?)\]/);
        if (!m) return null;
        try {
          const arr = JSON.parse('[' + m[1] + ']');
          return Array.isArray(arr) ? arr : null;
        } catch { return null; }
      };

      // Fallback: derive codes from inline mentions in the Assessment text, e.g.
      // "Essential Hypertension (I10) — ...". The model reliably writes codes inline
      // even when (for a returning patient) it leaves the structured array empty.
      const codesFromAssessment = (assessment) => {
        if (!assessment) return [];
        const seen = new Set();
        const out = [];
        const re = /([A-Za-z][A-Za-z0-9 ,'/\-]{2,60}?)\s*\(([A-TV-Z][0-9]{2}(?:\.[0-9A-Z]{1,4})?)\)/g;
        let m;
        while ((m = re.exec(assessment)) !== null) {
          const code = m[2];
          if (seen.has(code)) continue;
          seen.add(code);
          out.push({ code, description: m[1].replace(/^\d+[.)]\s*/, '').trim() });
        }
        return out;
      };

      // Ensure a note always carries ICD chips: if the structured array is empty,
      // fall back to codes parsed from the Assessment.
      const withIcdFallback = (n) => {
        if (n && (!n.icd10_codes || n.icd10_codes.length === 0)) {
          const derived = codesFromAssessment(n.assessment || '');
          if (derived.length) return { ...n, icd10_codes: derived };
        }
        return n;
      };

      let soapGenerated = false;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        sseBuffer += decoder.decode(value, { stream: true });
        const lines = sseBuffer.split('\n');
        sseBuffer = lines.pop() || '';
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const raw = line.slice(6).trim();
          if (raw === '[DONE]') {
            setStreamStatus('');
            // Robust final attempt: Claude sometimes wraps JSON in ```json fences
            // or adds a sentence of preamble. Strip fences and parse the last
            // brace-delimited object before deciding the stream truly failed.
            if (!soapGenerated) {
              const cleaned = accumulated.replace(/```json/gi, '').replace(/```/g, '');
              const k0 = cleaned.indexOf('{'), k1 = cleaned.lastIndexOf('}');
              if (k0 !== -1 && k1 > k0) {
                try {
                  const parsed = withIcdFallback(JSON.parse(cleaned.slice(k0, k1 + 1)));
                  if (parsed.subjective !== undefined) {
                    setNote(parsed); saveDraft(parsed); soapGenerated = true;
                  }
                } catch { /* genuinely unparseable */ }
              }
            }
            // Last-resort recovery: if a strict parse still failed but SOAP text
            // did stream in, accept it (a transient truncation must not discard a
            // visibly-generated note) and best-effort recover the ICD-10 codes.
            if (!soapGenerated) {
              const partial = extractPartialFields(accumulated);
              if (partial.subjective || partial.assessment || partial.plan) {
                const codes = extractIcdCodes(accumulated);
                const merged = withIcdFallback({
                  subjective: partial.subjective || '',
                  objective:  partial.objective  || '',
                  assessment: partial.assessment || '',
                  plan:       partial.plan       || '',
                  icd10_codes: codes || [],
                });
                setNote(merged); saveDraft(merged); soapGenerated = true;
              }
            }
            // Only surface an error if no usable SOAP was produced at all
            if (!soapGenerated) {
              setError('Could not generate a SOAP note from this transcript. '
                + 'Please ensure it describes a real clinical encounter, then try again.');
            }
            break;
          }
          try {
            const evt = JSON.parse(raw);
            if (evt.type === 'tool_result') {
              setStreamStatus('Retrieved patient history…');
              accumulated = '';
            } else if (evt.type === 'text') {
              accumulated += evt.text;
              const partial = extractPartialFields(accumulated);
              const liveCodes = extractIcdCodes(accumulated);
              if (Object.keys(partial).length > 0 || liveCodes) {
                setNote(prev => ({ ...prev, ...partial, ...(liveCodes ? { icd10_codes: liveCodes } : {}) }));
              }
              const j0 = accumulated.indexOf('{'), j1 = accumulated.lastIndexOf('}');
              if (j0 !== -1 && j1 > j0) {
                try {
                  const parsed = withIcdFallback(JSON.parse(accumulated.slice(j0, j1 + 1)));
                  if (parsed.subjective !== undefined) {
                    setNote(parsed); saveDraft(parsed);
                    soapGenerated = true;
                  }
                } catch {}
              }
            } else if (evt.type === 'insufficient') {
              // Backend detected insufficient clinical content before calling AI
              setNote(evt.note || {});
              setError('⚠ Not enough clinical content to generate a SOAP note. '
                + 'Please include patient symptoms, history, and clinical findings.');
              soapGenerated = true; // prevent double-error on [DONE]
            } else if (evt.type === 'content') {
              // Legacy fallback
              try { const p = JSON.parse(evt.text); setNote(p); soapGenerated = true; } catch {}
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

  // ── Save note → auto-lock as read-only ───────────────────────────────────
  const handleSave = async () => {
    setSaving(true);
    setError('');
    try {
      const { data } = await api.post('/encounters/save', {
        encounter_id: parseInt(id),
        content: note,
        raw_input: transcript,
        label: versionLabel.trim() || null,
      });
      setSaved(true);
      setIsDirty(false);
      setCurrentVersion(data.version_no);

      // Refresh versions list
      const { data: enc } = await api.get(`/encounters/${id}`);
      setVersions(enc.versions || []);

      // Auto-lock: page becomes read-only immediately after saving
      setIsReadOnly(true);
      setViewingVersion(data.version_no);
      setVersionBannerOpen(true);
      setVersionLabel('');

      setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      const status = err.response?.status;
      const detail = err.response?.data?.detail;
      setError(
        status === 401 ? 'Session expired. Draft preserved. Please log in again.'
        : status === 422 && detail ? detail
        : 'Save failed. Your draft is preserved.'
      );
    } finally {
      setSaving(false);
    }
  };

  const appendICD10 = (code) => {
    const codes = note.icd10_codes || [];
    if (codes.find(c => c.code === code.code)) return;
    const updated = { ...note, icd10_codes: [...codes, { code: code.code, description: code.description }] };
    setNote(updated); saveDraft(updated); markEdited();
  };

  const removeICD10 = (code) => {
    const updated = { ...note, icd10_codes: (note.icd10_codes || []).filter(c => c.code !== code) };
    setNote(updated); saveDraft(updated); markEdited();
  };

  if (!encounter) return (
    <div className="min-h-screen bg-clinical-bg flex items-center justify-center text-clinical-muted text-sm">
      Loading encounter…
    </div>
  );

  const patientId = encounter.patient?.id;
  const wordCount = versionLabel.trim() === '' ? 0 : versionLabel.trim().split(/\s+/).length;

  return (
    <div className="h-screen bg-clinical-bg flex flex-col overflow-hidden">

      {/* ── Session Expired Overlay ── */}
      {sessionExpired && (
        <div className="fixed inset-0 z-50 bg-clinical-bg/95 backdrop-blur-sm flex flex-col items-center justify-center p-8">
          <div className="w-full max-w-2xl card border-2 border-clinical-accent/60 p-8 space-y-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-full bg-clinical-accent/20 flex items-center justify-center shrink-0 mt-0.5">
                <svg className="w-5 h-5 text-clinical-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                </svg>
              </div>
              <div>
                <h2 className="text-base font-semibold text-clinical-text mb-1">Session Expired</h2>
                <p className="text-sm text-clinical-text-dim leading-relaxed">
                  Your session has timed out. Your draft has been automatically saved —
                  log in again to continue exactly where you left off.
                </p>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => { window.location.href = '/login'; }}
                className="btn-primary text-sm px-5 py-2"
              >Log in again</button>
              {transcript && (
                <button
                  onClick={() => navigator.clipboard.writeText(transcript)}
                  className="text-sm px-4 py-2 border border-clinical-border rounded text-clinical-muted hover:text-clinical-text transition-colors"
                >Copy transcript</button>
              )}
              {(note.subjective || note.assessment || note.plan) && (
                <button
                  onClick={() => navigator.clipboard.writeText(
                    `SUBJECTIVE
${note.subjective}

OBJECTIVE
${note.objective}

ASSESSMENT
${note.assessment}

PLAN
${note.plan}`
                  )}
                  className="text-sm px-4 py-2 border border-clinical-border rounded text-clinical-muted hover:text-clinical-text transition-colors"
                >Copy SOAP note</button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* -- Session Superseded Overlay -- */}
      {sessionSuperseded && (
        <div className="fixed inset-0 z-50 bg-clinical-bg/95 backdrop-blur-sm flex flex-col items-center justify-center p-8">
          <div className="w-full max-w-2xl card border-2 border-clinical-warning/60 p-8 space-y-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-full bg-clinical-warning/20 flex items-center justify-center shrink-0 mt-0.5">
                <svg className="w-5 h-5 text-clinical-warning" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <h2 className="text-base font-semibold text-clinical-text mb-1">Signed In on Another Device</h2>
                <p className="text-sm text-clinical-text-dim leading-relaxed">
                  Your account has been signed in on another device, so this session has been ended.
                  Your draft has been automatically saved &mdash; log in again to continue exactly where you left off.
                </p>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => { window.location.href = '/login'; }}
                className="btn-primary text-sm px-5 py-2"
              >Log in again</button>
              {transcript && (
                <button
                  onClick={() => navigator.clipboard.writeText(transcript)}
                  className="text-sm px-4 py-2 border border-clinical-border rounded text-clinical-muted hover:text-clinical-text transition-colors"
                >Copy transcript</button>
              )}
              {(note.subjective || note.assessment || note.plan) && (
                <button
                  onClick={() => navigator.clipboard.writeText(
                    `SUBJECTIVE\n${note.subjective}\n\nOBJECTIVE\n${note.objective}\n\nASSESSMENT\n${note.assessment}\n\nPLAN\n${note.plan}`
                  )}
                  className="text-sm px-4 py-2 border border-clinical-border rounded text-clinical-muted hover:text-clinical-text transition-colors"
                >Copy SOAP note</button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Account Deactivated Overlay ── */}
      {deactivated && (
        <div className="fixed inset-0 z-50 bg-clinical-bg/95 backdrop-blur-sm flex flex-col items-center justify-center p-8">
          <div className="w-full max-w-2xl card border-2 border-clinical-warning/60 p-8 space-y-6">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 rounded-full bg-clinical-warning/20 flex items-center justify-center shrink-0 mt-0.5">
                <svg className="w-5 h-5 text-clinical-warning" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                    d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
                </svg>
              </div>
              <div>
                <h2 className="text-base font-semibold text-clinical-text mb-1">Account Deactivated</h2>
                <p className="text-sm text-clinical-text-dim leading-relaxed">
                  Your account has been deactivated by an administrator. You can no longer save changes.
                  Please copy your note content below and contact your system administrator.
                </p>
              </div>
            </div>

            <div className="space-y-3">
              {transcript && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-clinical-muted uppercase tracking-wide">Transcript</span>
                    <button
                      onClick={() => navigator.clipboard.writeText(transcript)}
                      className="text-xs text-clinical-accent hover:underline"
                    >Copy</button>
                  </div>
                  <pre className="text-xs bg-clinical-bg border border-clinical-border rounded p-3 whitespace-pre-wrap max-h-32 overflow-y-auto text-clinical-text-dim">{transcript}</pre>
                </div>
              )}
              {(note.subjective || note.assessment || note.plan) && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-medium text-clinical-muted uppercase tracking-wide">SOAP Note</span>
                    <button
                      onClick={() => navigator.clipboard.writeText(
                        `SUBJECTIVE
${note.subjective}

OBJECTIVE
${note.objective}

ASSESSMENT
${note.assessment}

PLAN
${note.plan}`
                      )}
                      className="text-xs text-clinical-accent hover:underline"
                    >Copy</button>
                  </div>
                  <pre className="text-xs bg-clinical-bg border border-clinical-border rounded p-3 whitespace-pre-wrap max-h-48 overflow-y-auto text-clinical-text-dim">{
                    `SUBJECTIVE
${note.subjective}

OBJECTIVE
${note.objective}

ASSESSMENT
${note.assessment}

PLAN
${note.plan}`
                  }</pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Header h-14 ── */}
      <header className="border-b border-clinical-border bg-clinical-surface h-14 px-5 flex items-center justify-between shrink-0 relative">

        {/* Left */}
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <button
            onClick={() => patientId ? navigate(`/patient/${patientId}`, { state: { adminView: isAdmin } }) : navigate(isAdmin ? '/admin' : '/')}
            className="text-sm font-semibold text-white hover:text-clinical-accent transition-colors shrink-0"
          >← Back</button>
          <div className="w-px h-4 bg-clinical-border shrink-0" />
          <span className="text-sm font-medium text-clinical-text truncate">
            {encounter.patient?.first_name} {encounter.patient?.last_name}
          </span>
          <span className="text-xs text-clinical-muted shrink-0 hidden sm:inline">DOB: {encounter.patient?.dob}</span>
          {isAdmin ? (
            encounter.template_name && (
              <span className="tag bg-clinical-accent/10 text-clinical-accent text-xs shrink-0">
                {encounter.template_name}
              </span>
            )
          ) : (
            <div className="relative shrink-0" ref={templatePickerRef}>
              <button
                onClick={() => {
                  if (deactivated || sessionExpired || sessionSuperseded) return;
                  // Re-fetch templates on every open so admin changes are immediately visible
                  api.get('/admin/templates').then(r => {
                    setTemplates((r.data || []).filter(t => t.is_active));
                  }).catch(() => {});
                  setTemplatePickerOpen(o => !o);
                }}
                className="tag bg-clinical-accent/10 text-clinical-accent text-xs hover:bg-clinical-accent/20 transition-colors flex items-center gap-1 cursor-pointer"
                title="Click to change template"
              >
                {templates.find(t => t.id === activeTemplateId)?.name ?? 'No template'}
                <svg className="w-3 h-3 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {templatePickerOpen && (
                <div className="absolute top-full left-0 mt-1 w-60 bg-clinical-surface border border-clinical-border rounded-lg shadow-xl z-30 py-1 overflow-hidden">
                  <div className="px-3 py-1.5 border-b border-clinical-border">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-clinical-muted">Select template</span>
                  </div>
                  <button
                    onClick={() => handleTemplateChange(null)}
                    className={`w-full text-left px-3 py-2 text-xs transition-colors hover:bg-clinical-border/30 ${
                      activeTemplateId === null ? 'text-clinical-accent font-semibold' : 'text-clinical-text-dim'
                    }`}
                  >
                    No template
                  </button>
                  {templates.map(t => (
                    <button
                      key={t.id}
                      onClick={() => handleTemplateChange(t.id)}
                      className={`w-full text-left px-3 py-2 text-xs transition-colors hover:bg-clinical-border/30 ${
                        activeTemplateId === t.id ? 'text-clinical-accent font-semibold' : 'text-clinical-text'
                      }`}
                    >
                      {t.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Center: last editing time (only when unsaved edits exist) */}
        {isDirty && lastEditTime && (
          <div className="absolute left-1/2 -translate-x-1/2 text-xs text-clinical-muted pointer-events-none whitespace-nowrap">
            Last edit: {lastEditTime.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </div>
        )}

        {/* Right */}
        <div className="flex items-center gap-2 shrink-0 flex-1 justify-end">
          {isReadOnly
            ? <span className="text-xs text-clinical-muted">Read-only</span>
            : null
          }
          <span className={`tag text-xs ${encounter.status === 'saved' ? 'bg-clinical-success/10 text-clinical-success' : 'bg-clinical-warning/10 text-clinical-warning'}`}>
            {encounter.status === 'saved' ? '✓ Submitted' : '⚠ Draft'}
          </span>
          {!isReadOnly && (
            <button onClick={handleSave} disabled={saving || streaming || hasNoteIssue} title={hasNoteIssue ? "Note content is incomplete — cannot submit" : undefined} className="btn-primary text-xs py-1.5 disabled:opacity-40 disabled:cursor-not-allowed">
              {saving ? 'Saving…' : saved ? '✓ Saved' : 'Save Note'}
            </button>
          )}
          {isReadOnly && !isAdmin && (
            <button
              onClick={() => {
                setIsReadOnly(false);
                setIsDirty(false);
                setLastEditTime(null);
              }}
              className="btn-primary text-xs py-1.5"
            >New version</button>
          )}
          <button
            onClick={logout}
            className="text-xs border border-clinical-danger text-clinical-danger hover:bg-clinical-danger/10 px-3 py-1.5 rounded transition-colors"
          >Sign out</button>
        </div>
      </header>

      {/* Error banner */}
      {error && (
        <div className="bg-clinical-danger/10 border-b border-clinical-danger/20 px-5 py-2 text-sm text-clinical-danger shrink-0 flex items-center justify-between">
          {error}
          <button onClick={() => setError('')} className="text-clinical-danger/60 hover:text-clinical-danger ml-3">✕</button>
        </div>
      )}

      {/* ── Read-only banner with collapsible version history ── */}
      {isReadOnly && (
        <div className="bg-clinical-surface border-b border-clinical-border shrink-0">
          <div className="px-5 py-2.5 flex items-center justify-between">
            <span className="text-xs text-clinical-warning font-medium">
              {isAdmin ? '🔒 Admin view · read-only' : '⚠ This note has been submitted and is read-only.'}
            </span>
            {versions.length > 0 && (
              <button
                onClick={() => setVersionBannerOpen(v => !v)}
                className="text-xs text-clinical-text-dim hover:text-clinical-text flex items-center gap-1.5 transition-colors"
              >
                Version History
                <span>{versionBannerOpen ? '▲' : '▼'}</span>
              </button>
            )}
          </div>

          {/* ── insufficient note warning (admin + provider) ── */}
          {hasNoteIssue && (
            <div className="border-t border-clinical-border/50 px-4 py-2.5 flex items-center gap-2 bg-clinical-danger/5">
              <svg className="w-3.5 h-3.5 text-clinical-danger shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" />
              </svg>
                    <span className="text-xs text-clinical-danger">
        {!aiContentValid
          ? "AI detected invalid content — remove non-clinical text before saving."
          : "This note appears incomplete — the transcript may not contain sufficient clinical content."}
        {aiValidating && <span className="ml-2 opacity-60">(checking…)</span>}
      </span>
            </div>
          )}

          {versionBannerOpen && versions.length > 0 && (
            <div className="border-t border-clinical-border/50 px-5 py-2 space-y-1">
              {[...versions].map(v => {
                const isViewing = v.version_no === viewingVersion;
                const label = v.content?.__label;
                return (
                  <button
                    key={v.version_no}
                    onClick={() => {
                      const { __label, _transcript, ...noteContent } = v.content;
                      setNote(noteContent);
                      // Restore this version's transcript snapshot if available
                      const tx = _transcript ?? encounter?.raw_input ?? '';
                      setTranscript(tx);
                      transcriptRef.current = tx;
                      setViewingVersion(v.version_no);
                      api.post(`/encounters/${id}/view-version/${v.version_no}`).catch(() => {});
                    }}
                    disabled={isViewing}
                    className={`w-full text-left flex items-center gap-3 text-xs rounded px-2 py-1.5 transition-colors
                      ${isViewing ? 'bg-clinical-accent/10 cursor-default' : 'hover:bg-clinical-border/30 cursor-pointer'}`}
                  >
                    <span className="font-mono font-semibold text-clinical-text w-6 shrink-0">v{v.version_no}</span>
                    {label && (
                      <span className="text-clinical-accent italic shrink-0">"{label}"</span>
                    )}
                    <span className="text-clinical-muted">{fmtET(v.saved_at)}</span>
                    <span className="text-clinical-border">·</span>
                    <span className="text-clinical-text-dim">{v.saved_by_name}</span>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* ── Scrollable body ── */}
      <div className="flex-1 overflow-y-auto">

        {/* ── Version label — always visible above transcript ── */}
        <div className="border-b border-clinical-border bg-clinical-surface/50 px-5 py-2 flex items-center gap-3">
          <label className="text-xs text-clinical-muted whitespace-nowrap shrink-0">Version label</label>
          {isReadOnly ? (
            <span className="text-xs text-clinical-accent italic">
              {versions.find(v => v.version_no === viewingVersion)?.content?.__label
                || <span className="text-clinical-muted italic">—</span>}
            </span>
          ) : (
            <>
              <input
                className="flex-1 bg-clinical-bg border border-clinical-border rounded px-3 py-1.5 text-xs text-clinical-text focus:outline-none focus:border-clinical-accent/50 transition-colors"
                placeholder="Optional · max 4 words (e.g. initial assessment)"
                value={versionLabel}
                onChange={e => handleLabelChange(e.target.value)}
                maxLength={60}
              />
              <span className={`text-xs shrink-0 tabular-nums ${wordCount >= 4 ? 'text-clinical-warning' : 'text-clinical-muted'}`}>
                {wordCount}/4
              </span>
            </>
          )}
        </div>

        {/* ── Transcript — top, full width, fixed height, no resize ── */}
        <div className="border-b border-clinical-border bg-clinical-surface px-5 py-3 shrink-0">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-clinical-text-dim uppercase tracking-wider">
              Transcript / Observations
            </span>
            {streaming && (
              <span className="text-xs text-clinical-accent animate-pulse">{streamStatus}</span>
            )}
          </div>
          <textarea
            className="w-full bg-clinical-bg border border-clinical-border rounded-lg p-3 text-sm font-mono text-clinical-text focus:outline-none focus:border-clinical-accent/50 transition-colors leading-relaxed"
            style={{ height: '42vh', resize: 'none' }}
            value={transcript}
            onChange={e => {
              const val = e.target.value;
              setTranscript(val);
              transcriptRef.current = val;
              markEdited();
              // Save transcript to draft immediately (SOAP fields saved too)
              saveDraft(noteRef.current, val);
            }}
            placeholder="Paste encounter transcript or type clinical observations…"
            readOnly={isReadOnly}
          />
          {!isReadOnly && (
            <div className="mt-2 flex items-center gap-2">
              <button
                onClick={handleGenerate}
                disabled={streaming || !transcript.trim()}
                className="btn-primary flex items-center gap-2"
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
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z"/>
                    </svg>
                    Generate Note
                  </>
                )}
              </button>
              {streaming && (
                <button
                  onClick={() => abortRef.current?.abort()}
                  className="btn-ghost text-xs text-clinical-danger border-clinical-danger/30"
                >Stop</button>
              )}
            </div>
          )}
        </div>

        {/* ── SOAP accordion ── */}
        <div className="px-5 py-4 space-y-3">
          <SOAPSection field="subjective" value={note.subjective}
            onChange={v => updateNoteField('subjective', v)}
            streaming={streaming} prevFilled={true} readOnly={isReadOnly} />

          <SOAPSection field="objective" value={note.objective}
            onChange={v => updateNoteField('objective', v)}
            streaming={streaming} prevFilled={!!note.subjective} readOnly={isReadOnly} />

          <SOAPSection field="assessment" value={note.assessment}
            onChange={v => updateNoteField('assessment', v)}
            streaming={streaming} prevFilled={!!note.objective} readOnly={isReadOnly}>
            {(note.icd10_codes?.length > 0) && (
              <div className="mt-3 pt-3 border-t border-clinical-border">
                <div className="text-xs font-semibold text-clinical-text-dim uppercase tracking-wider mb-2">ICD-10 Codes</div>
                <div className="flex flex-wrap gap-2">
                  {note.icd10_codes.map(c => (
                    <span key={c.code} className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md bg-clinical-surface border border-clinical-border group cursor-default">
                      <span className="font-mono font-semibold text-sm text-clinical-success">{c.code}</span>
                      <span className="text-clinical-text-dim text-xs">{c.description}</span>
                      {!isReadOnly && (
                        <button onClick={() => removeICD10(c.code)} className="opacity-0 group-hover:opacity-100 text-clinical-danger text-xs ml-0.5 leading-none">✕</button>
                      )}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </SOAPSection>

          <SOAPSection field="plan" value={note.plan}
            onChange={v => updateNoteField('plan', v)}
            streaming={streaming} prevFilled={!!note.assessment} readOnly={isReadOnly} />
        </div>

        {/* ── Bottom tools: ICD-10 + version history (editing only) ── */}
        {!isReadOnly && (
          <div className="mx-5 mb-6 border border-clinical-border rounded-lg bg-clinical-surface divide-y divide-clinical-border">
            <div className="px-4 py-3">
              <ICD10Search onAppend={appendICD10} />
            </div>
            {versions.length >= 1 && (
              <div className="px-4 py-3">
                <VersionHistory
                  versions={versions}
                  currentVersion={currentVersion}
                  defaultExpanded={false}
                  onLoadVersion={(v) => {
                    const { __label, ...noteContent } = v.content;
                    setNote(noteContent);
                    markEdited();
                  }}
                />
              </div>
            )}
          </div>
        )}
        {/* ── Version diff: visible in both read-only and edit mode ── */}
        {versions.length >= 2 && (
          <div className="mx-5 mb-6 border border-clinical-border rounded-lg bg-clinical-surface px-4 py-3">
            <button
              onClick={() => setShowDiff(v => !v)}
              className="text-xs text-clinical-muted hover:text-clinical-text transition-colors"
            >
              {showDiff ? '▲ Hide diff' : '▼ Show version diff'}
            </button>
            {showDiff && <DiffView versions={versions} />}
          </div>
        )}

      </div>
    </div>
  );
}
