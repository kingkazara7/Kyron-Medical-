import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import api from '../api';

// ── Back dropdown — shown on level 2 (PatientHistory) ─────────────────────
function BackDropdown({ currentPatient, navigate }) {
  const [open, setOpen] = useState(false);
  const [othersExpanded, setOthersExpanded] = useState(false);
  const [others, setOthers] = useState([]);
  const ref = useRef(null);

  useEffect(() => {
    api.get('/encounters').then(r => {
      const seen = new Set([currentPatient.id]);
      const list = [];
      for (const e of r.data) {
        if (!seen.has(e.patient_id)) {
          seen.add(e.patient_id);
          list.push({ id: e.patient_id, name: e.patient_name });
        }
      }
      setOthers(list.slice(0, 10));
    }).catch(() => {});
  }, [currentPatient.id]);

  useEffect(() => {
    const handler = e => {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
        setOthersExpanded(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className="relative shrink-0">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1 text-sm font-semibold text-white hover:text-clinical-accent transition-colors"
      >
        ← Back
        <svg className={`w-3 h-3 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute top-full left-0 mt-2 bg-clinical-surface border border-clinical-border rounded-lg shadow-xl z-50 min-w-[220px] overflow-hidden">

          {/* Current patient — informational header */}
          <div className="px-3 py-2.5 border-b border-clinical-border bg-clinical-bg/50">
            <div className="text-xs text-clinical-muted uppercase tracking-wider mb-0.5">Current patient</div>
            <div className="text-sm font-medium text-clinical-text">
              {currentPatient.first_name} {currentPatient.last_name}
            </div>
          </div>

          {/* Other patients — collapsible submenu */}
          {others.length > 0 && (
            <div className="border-b border-clinical-border">
              {/* Clickable header row — toggles submenu */}
              <button
                onClick={() => setOthersExpanded(e => !e)}
                className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-clinical-border/20 transition-colors"
              >
                <span className="text-xs text-clinical-muted uppercase tracking-wider">Other patients</span>
                <svg
                  className={`w-3 h-3 text-clinical-muted transition-transform ${othersExpanded ? 'rotate-90' : ''}`}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
                </svg>
              </button>

              {/* Patient list — shown when expanded */}
              {othersExpanded && (
                <div className="bg-clinical-bg/30">
                  {others.map(p => (
                    <button
                      key={p.id}
                      onClick={() => { navigate(`/patient/${p.id}`); setOpen(false); setOthersExpanded(false); }}
                      className="w-full text-left pl-5 pr-3 py-2 text-sm text-clinical-text hover:bg-clinical-accent/10 hover:text-clinical-accent transition-colors flex items-center gap-2"
                    >
                      <span className="text-clinical-border text-xs">→</span>
                      {p.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Main page */}
          <button
            onClick={() => { navigate('/'); setOpen(false); setOthersExpanded(false); }}
            className="w-full text-left px-3 py-2.5 text-sm text-clinical-text hover:bg-clinical-border/30 transition-colors flex items-center gap-2"
          >
            <span className="text-clinical-muted">↩</span> Main page
          </button>
        </div>
      )}
    </div>
  );
}

// Format ISO timestamp → Eastern Time
function fmt(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-US', {
    timeZone: 'America/New_York',
    month: 'short', day: 'numeric', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}
function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-US', {
    timeZone: 'America/New_York',
    month: 'short', day: 'numeric', year: 'numeric',
  });
}

// ── Single encounter row (expandable) ──────────────────────────────────────
function EncounterRow({ enc, onDeleted, isAdminView = false }) {
  const [open, setOpen] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const navigate = useNavigate();

  const isDraft     = enc.status === 'draft';
  const isSubmitted = enc.status === 'saved';
  const isInvalid   = !!(enc.is_invalid);        // admin: empty/insufficient note
  // submitted encounter with unsaved edits in progress
  const hasPendingDraft = isSubmitted && enc.has_draft;

  const handleDelete = async () => {
    if (!deleteConfirm) { setDeleteConfirm(true); return; }
    setDeleting(true);
    try {
      await api.delete(`/encounters/${enc.encounter_id}`);
      onDeleted(enc.encounter_id);
    } catch {
      setDeleting(false);
      setDeleteConfirm(false);
    }
  };

  return (
    <div className={`card overflow-hidden ${
      isInvalid && isAdminView ? 'border-clinical-danger/30' :
      isDraft ? 'border-clinical-warning/30' : ''
    }`}>

      {/* ── Main bar — click to expand/collapse ── */}
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full text-left px-5 py-4 hover:bg-clinical-border/10 transition-colors"
      >
        <div className="flex items-start justify-between gap-4">

          {/* Left block */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="font-semibold text-sm text-clinical-text">{fmtDate(enc.created_at)}</span>

              {enc.template_name && (
                <span className="text-xs px-2 py-0.5 rounded border border-clinical-accent/30 text-clinical-accent">
                  {enc.template_name}
                </span>
              )}

              {isDraft && !isInvalid && (
                <span className="text-xs px-2 py-0.5 rounded border border-clinical-warning/40 bg-clinical-warning/10 text-clinical-warning">
                  ✏ Draft in progress
                </span>
              )}
              {isDraft && isInvalid && (
                <span className="text-xs px-2 py-0.5 rounded border border-clinical-danger/40 bg-clinical-danger/10 text-clinical-danger">
                  ✗ Invalid draft
                </span>
              )}
              {isSubmitted && !hasPendingDraft && (
                <span className="text-xs px-2 py-0.5 rounded border border-clinical-success/40 bg-clinical-success/10 text-clinical-success">
                  ✓ Submitted
                </span>
              )}
              {hasPendingDraft && (
                <span className="text-xs px-2 py-0.5 rounded border border-clinical-warning/40 bg-clinical-warning/10 text-clinical-warning">
                  ✏ Draft in progress
                </span>
              )}
            </div>

            <div className="text-xs text-clinical-muted mt-1.5 flex flex-wrap gap-x-4 gap-y-0.5">
              {isSubmitted && enc.submitted_at && (
                <span>Submitted: {fmt(enc.submitted_at)}</span>
              )}
              {isDraft && enc.last_saved_at && (
                <span>Last saved: {fmt(enc.last_saved_at)}</span>
              )}
              {isDraft && !enc.last_saved_at && (
                <span>Last edited: {fmt(enc.updated_at)}</span>
              )}
              {enc.version_count > 0 && (
                <span className="text-clinical-border">· {enc.version_count} version{enc.version_count !== 1 ? 's' : ''}</span>
              )}
            </div>

            {enc.summary && (
              <div className="text-xs text-clinical-text-dim mt-2 leading-relaxed">
                <span className="text-clinical-muted">Reason: </span>
                {enc.summary.reason}
              </div>
            )}
          </div>

          <span className="text-xs text-clinical-muted shrink-0 mt-0.5">{open ? '▲' : '▼'}</span>
        </div>
      </button>

      {/* ── Expanded detail panel ── */}
      {open && (
        <div className="border-t border-clinical-border bg-clinical-bg/40">

          {/* Version list */}
          {(enc.versions && enc.versions.length > 0) || hasPendingDraft ? (
            <div className="px-5 py-3 space-y-1">
              <div className="text-xs font-semibold text-clinical-text-dim uppercase tracking-wider mb-2">
                Version History
              </div>
              {[...enc.versions].map((v, idx) => {
                const isLatest = idx === enc.versions.length - 1 && !hasPendingDraft;
                const label = v.label || v.content?.__label;
                return (
                  <button
                    key={v.version_no}
                    onClick={() => navigate(`/encounter/${enc.encounter_id}`, { state: { viewVersion: v.version_no } })}
                    className="w-full text-left flex items-center justify-between text-xs rounded px-2 py-1.5 hover:bg-clinical-border/30 transition-colors cursor-pointer"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-semibold text-clinical-text">v{v.version_no}</span>
                      {isLatest && (
                        <span className="px-1.5 py-0.5 rounded text-clinical-accent bg-clinical-accent/10 border border-clinical-accent/20 text-xs">
                          latest
                        </span>
                      )}
                      {label && (
                        <span className="text-clinical-accent italic">"{label}"</span>
                      )}
                      <span className="text-clinical-muted">
                        {fmt(v.saved_at)} · {v.saved_by_name}
                      </span>
                    </div>
                    <span className="text-clinical-accent text-xs">View →</span>
                  </button>
                );
              })}

              {/* Draft-in-progress row — at the bottom of version list */}
              {hasPendingDraft && (
                <button
                  onClick={() => navigate(`/encounter/${enc.encounter_id}`)}
                  className="w-full text-left flex items-center justify-between text-xs rounded px-2 py-1.5 bg-clinical-warning/5 border border-clinical-warning/20 hover:bg-clinical-warning/10 transition-colors cursor-pointer"
                >
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-semibold text-clinical-warning">draft</span>
                    <span className="px-1.5 py-0.5 rounded text-clinical-warning bg-clinical-warning/10 border border-clinical-warning/20 text-xs">
                      unsaved edits
                    </span>
                    <span className="text-clinical-muted italic">not yet saved as a version</span>
                  </div>
                  <span className="text-clinical-warning text-xs">Continue →</span>
                </button>
              )}
            </div>
          ) : null}

          {/* Action buttons */}
          <div className="px-5 py-3 border-t border-clinical-border/50 flex items-center justify-between">
            <span className="text-xs text-clinical-muted">Encounter #{enc.encounter_id}</span>
            {isAdminView ? (
              <button
                onClick={() => navigate(`/encounter/${enc.encounter_id}`)}
                className="btn-ghost text-xs border border-clinical-border"
              >View note →</button>
            ) : (
            <div className="flex items-center gap-2">
              {isDraft ? (
                <>
                  {/* Delete draft — two-click confirm */}
                  <button
                    onClick={handleDelete}
                    disabled={deleting}
                    className={`text-xs px-3 py-1.5 rounded border transition-colors ${
                      deleteConfirm
                        ? 'border-clinical-danger bg-clinical-danger/10 text-clinical-danger hover:bg-clinical-danger/20'
                        : 'border-clinical-border text-clinical-muted hover:border-clinical-danger/40 hover:text-clinical-danger'
                    }`}
                  >
                    {deleting ? 'Deleting…' : deleteConfirm ? 'Confirm delete' : 'Delete'}
                  </button>
                  {deleteConfirm && !deleting && (
                    <button
                      onClick={() => setDeleteConfirm(false)}
                      className="text-xs text-clinical-muted hover:text-clinical-text transition-colors"
                    >Cancel</button>
                  )}
                  <button
                    onClick={() => navigate(`/encounter/${enc.encounter_id}`)}
                    className="btn-primary text-xs"
                  >
                    Continue editing →
                  </button>
                </>
              ) : (
                <>
                  {hasPendingDraft ? (
                    /* Resume the unsaved draft (workspace auto-detects and unlocks) */
                    <button
                      onClick={() => navigate(`/encounter/${enc.encounter_id}`)}
                      className="btn-primary text-xs"
                    >
                      Continue draft →
                    </button>
                  ) : (
                    /* No draft — start a new version */
                    <button
                      onClick={() => navigate(`/encounter/${enc.encounter_id}`, { state: { newVersion: true } })}
                      className="btn-ghost text-xs border border-clinical-accent/40 text-clinical-accent hover:bg-clinical-accent/10"
                    >
                      New version
                    </button>
                  )}
                  <button
                    onClick={() => navigate(`/encounter/${enc.encounter_id}`)}
                    className="btn-ghost text-xs border border-clinical-border"
                  >
                    View note →
                  </button>
                </>
              )}
            </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Modal: start a new encounter for an existing patient ───────────────────
function NewEncounterModal({ patient, onClose, onCreated }) {
  const [templates, setTemplates] = useState([]);
  const [templateId, setTemplateId] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get('/admin/templates').then(r => setTemplates(r.data)).catch(() => {});
  }, []);

  const handleSubmit = async e => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const { data } = await api.post('/encounters', {
        patient: { first_name: patient.first_name, last_name: patient.last_name, dob: patient.dob },
        template_id: templateId ? parseInt(templateId) : null,
      });
      onCreated(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-sm p-6">
        <div className="flex items-center justify-between mb-4">
          <span className="font-semibold text-base">New Encounter</span>
          <button onClick={onClose} className="text-clinical-muted hover:text-clinical-text">✕</button>
        </div>
        <div className="text-sm text-clinical-text-dim mb-4">
          {patient.first_name} {patient.last_name} · DOB: {patient.dob}
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="label">Template (optional)</label>
            <select className="input" value={templateId} onChange={e => setTemplateId(e.target.value)}>
              <option value="">No template</option>
              {templates.filter(t => t.is_active).map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
          {error && <div className="text-clinical-danger text-sm">{error}</div>}
          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onClose} className="btn-ghost flex-1">Cancel</button>
            <button type="submit" disabled={loading} className="btn-primary flex-1">
              {loading ? 'Creating…' : 'Start Encounter'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Patient History page ───────────────────────────────────────────────────
export default function PatientHistory() {
  const { patientId } = useParams();
  const { logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [encounters, setEncounters] = useState([]);
  const [showModal, setShowModal] = useState(false);

  const isAdminView = !!(location.state?.adminView);

  // Auto-open New Encounter modal if navigated from Dashboard's "New Encounter" button
  useEffect(() => {
    if (location.state?.openNewEncounter && !isAdminView) {
      setShowModal(true);
    }
  }, []);

  const load = () => {
    const url = isAdminView
      ? `/admin/patients/${patientId}/encounters`
      : `/encounters/patient/${patientId}`;
    api.get(url)
      .then(r => {
        setData(r.data);
        setEncounters(r.data.encounters || []);
      })
      .catch(() => navigate(isAdminView ? '/admin' : '/'))
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [patientId]);

  const handleCreated = enc => {
    setShowModal(false);
    navigate(`/encounter/${enc.encounter_id}`);
  };

  const handleDeleted = (encounterId) => {
    setEncounters(prev => prev.filter(e => e.encounter_id !== encounterId));
  };

  if (loading) return (
    <div className="min-h-screen bg-clinical-bg flex items-center justify-center text-clinical-muted text-sm">
      Loading…
    </div>
  );

  const patient  = data?.patient;
  const hasDraft = encounters.some(e => e.status === 'draft');

  return (
    <div className="min-h-screen bg-clinical-bg">

      {/* ── Header — same h-14 as Dashboard ── */}
      <header className="border-b border-clinical-border bg-clinical-surface h-14 px-4 sm:px-6 grid grid-cols-[1fr_auto_1fr] items-center shrink-0">

        {/* Left: back / admin button */}
        <div className="flex items-center min-w-0">
          {isAdminView ? (
            <button
              onClick={() => navigate('/admin')}
              className="flex items-center gap-1 text-sm font-semibold text-white hover:text-clinical-accent transition-colors whitespace-nowrap"
            >
              ← Admin
            </button>
          ) : (
            patient && <BackDropdown currentPatient={patient} navigate={navigate} />
          )}
        </div>

        {/* Center: patient identity — no absolute positioning */}
        <div className="text-center pointer-events-none px-2">
          <div className="font-semibold text-sm text-clinical-text whitespace-nowrap">
            {patient?.first_name} {patient?.last_name}
          </div>
          <div className="text-xs text-clinical-muted hidden sm:block">DOB: {patient?.dob}</div>
        </div>

        {/* Right: admin badge + sign out */}
        <div className="flex items-center gap-2 justify-end">
          {isAdminView && (
            <span className="text-xs px-2 py-1 rounded border border-clinical-accent/30 text-clinical-accent bg-clinical-accent/5 hidden sm:inline">
              Admin · Read-only
            </span>
          )}
          <button
            onClick={logout}
            className="text-xs border border-clinical-danger text-clinical-danger hover:bg-clinical-danger/10 px-2.5 py-1.5 rounded transition-colors whitespace-nowrap"
          >
            Sign out
          </button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">

        {/* Patient summary row */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="font-semibold text-base text-clinical-text">
              {patient?.first_name} {patient?.last_name}
            </h1>
            <p className="text-xs text-clinical-muted mt-0.5">
              DOB: {patient?.dob}
              &nbsp;·&nbsp;{encounters.length} encounter{encounters.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>

        <div className="space-y-3">
          {encounters.map(enc => (
            <EncounterRow
              key={enc.encounter_id}
              enc={enc}
              onDeleted={handleDeleted}
              isAdminView={isAdminView}
            />
          ))}

          {/* ── New Encounter card — hidden in admin view ── */}
          {!isAdminView && <button
            onClick={() => setShowModal(true)}
            className="w-full border border-dashed border-clinical-accent/40 rounded-lg px-5 py-4 text-left bg-clinical-accent/5 hover:bg-clinical-accent/10 hover:border-clinical-accent/70 transition-colors flex items-center gap-3"
          >
            <div className="w-7 h-7 rounded-md border border-clinical-accent/50 bg-clinical-accent/10 flex items-center justify-center text-clinical-accent text-base leading-none font-bold">
              +
            </div>
            <div>
              <div className="text-sm font-semibold text-clinical-accent">New Encounter</div>
              <div className="text-xs text-clinical-text-dim">Start a new encounter for this patient</div>
            </div>
          </button>}
        </div>
      </main>

      {showModal && patient && !isAdminView && (
        <NewEncounterModal
          patient={patient}
          onClose={() => setShowModal(false)}
          onCreated={handleCreated}
        />
      )}
    </div>
  );
}
