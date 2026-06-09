import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import api from '../api';

function NewPatientModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ first_name: '', last_name: '', dob: '', template_id: '' });
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => { api.get('/admin/templates').then(r => setTemplates(r.data)).catch(() => {}); }, []);
  const handleSubmit = async e => {
    e.preventDefault(); setLoading(true); setError('');
    try {
      const { data } = await api.post('/encounters', {
        patient: { first_name: form.first_name, last_name: form.last_name, dob: form.dob },
        template_id: form.template_id ? parseInt(form.template_id) : null,
      });
      onCreated(data);
    } catch (err) { setError(err.response?.data?.detail || 'Failed'); }
    finally { setLoading(false); }
  };
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-5">
          <h2 className="font-semibold text-base">New Patient</h2>
          <button onClick={onClose} className="text-clinical-muted hover:text-clinical-text">x</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div><label className="label">First Name</label>
              <input className="input" value={form.first_name} onChange={e => setForm(f => ({...f, first_name: e.target.value}))} required /></div>
            <div><label className="label">Last Name</label>
              <input className="input" value={form.last_name} onChange={e => setForm(f => ({...f, last_name: e.target.value}))} required /></div>
          </div>
          <div><label className="label">Date of Birth</label>
            <input type="date" className="input" value={form.dob} onChange={e => setForm(f => ({...f, dob: e.target.value}))} required /></div>
          <div><label className="label">Template (optional)</label>
            <select className="input" value={form.template_id} onChange={e => setForm(f => ({...f, template_id: e.target.value}))}>
              <option value="">No template</option>
              {templates.filter(t => t.is_active).map(t => (<option key={t.id} value={t.id}>{t.name}</option>))}
            </select></div>
          {error && <div className="text-clinical-danger text-sm">{error}</div>}
          <div className="flex gap-2 pt-1">
            <button type="button" onClick={onClose} className="btn-ghost flex-1">Cancel</button>
            <button type="submit" disabled={loading} className="btn-primary flex-1">{loading ? 'Creating...' : 'Start Encounter'}</button>
          </div>
        </form>
      </div>
    </div>
  );
}

function fmtDate(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('en-US', {
    timeZone: 'America/New_York', month: 'short', day: 'numeric', year: 'numeric',
  });
}

export default function Dashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [encounters, setEncounters] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(true);

  // Admin accounts do not use the provider dashboard — redirect immediately
  useEffect(() => {
    if (user?.role === 'admin') navigate('/admin', { replace: true });
  }, [user, navigate]);

  useEffect(() => {
    if (user?.role === 'admin') return;
    api.get('/encounters').then(r => setEncounters(r.data)).finally(() => setLoading(false));
  }, [user]);

  // One row per patient — deduplicate encounters by patient_id
  const patients = useMemo(() => {
    const map = new Map();
    for (const enc of encounters) {
      if (!map.has(enc.patient_id)) {
        map.set(enc.patient_id, {
          patientId: enc.patient_id,
          patientName: enc.patient_name,
          lastDate: enc.updated_at,
          encs: [],
        });
      }
      const p = map.get(enc.patient_id);
      if (new Date(enc.updated_at) > new Date(p.lastDate)) p.lastDate = enc.updated_at;
      p.encs.push(enc);
    }
    return Array.from(map.values()).map(p => ({
      ...p,
      invalidCount: p.encs.filter(e => e.is_invalid).length,
      draftCount:   p.encs.filter(e => (e.status === 'draft' || e.has_draft) && !e.is_invalid).length,
    }));
  }, [encounters]);

  const handleCreated = data => {
    setShowModal(false);
    navigate(`/patient/${data.patient_id}`);
  };

  // Admin accounts are redirected by the useEffect above — render nothing
  if (user?.role === 'admin') return null;

  return (
    <div className="min-h-screen bg-clinical-bg">
      <header className="border-b border-clinical-border bg-clinical-surface h-14 px-4 sm:px-6 grid grid-cols-[1fr_auto_1fr] items-center shrink-0">
        {/* Left — empty spacer so title stays truly centred */}
        <div />
        {/* Center title — no absolute positioning needed */}
        <span className="font-semibold text-sm text-clinical-text tracking-wide whitespace-nowrap">Patients</span>
        {/* Right — actions flush to the right edge */}
        <div className="flex items-center gap-2 justify-end">
          <span className="text-sm text-clinical-text-dim hidden sm:inline truncate max-w-[120px]">{user?.name}</span>
          {user?.role === 'admin' && (
            <button onClick={() => navigate('/admin')} className="text-xs border border-clinical-border text-clinical-text-dim hover:border-clinical-accent/50 hover:text-clinical-text px-2.5 py-1.5 rounded transition-colors hidden sm:inline-flex">Admin</button>
          )}
          <button onClick={logout} className="text-xs border border-clinical-danger text-clinical-danger hover:bg-clinical-danger/10 px-2.5 py-1.5 rounded transition-colors whitespace-nowrap">Sign out</button>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">
        {loading ? (
          <div className="text-clinical-muted text-sm text-center py-12">Loading...</div>
        ) : (
          <div className="space-y-2">
            {patients.map(p => (
              <div
                key={p.patientId}
                onClick={() => navigate(`/patient/${p.patientId}`)}
                className="card px-5 py-3.5 flex items-center justify-between gap-4 cursor-pointer hover:border-clinical-accent/40 transition-colors"
              >
                {/* Left: name + status dots */}
                <div className="flex items-center gap-3 min-w-0">
                  <span className="font-semibold text-sm text-clinical-text truncate">{p.patientName}</span>
                  <div className="flex items-center gap-2 shrink-0">
                    {p.invalidCount === 0 && p.draftCount === 0 ? null : (
                      <>
                        {p.invalidCount > 0 && (
                          <span className="flex items-center gap-1 text-xs text-clinical-danger" title={`${p.invalidCount} invalid`}>
                            <span className="w-2 h-2 rounded-full bg-clinical-danger shrink-0" />
                            {p.invalidCount}
                          </span>
                        )}
                        {p.draftCount > 0 && (
                          <span className="flex items-center gap-1 text-xs text-clinical-warning" title={`${p.draftCount} in progress`}>
                            <span className="w-2 h-2 rounded-full bg-clinical-warning shrink-0" />
                            {p.draftCount}
                          </span>
                        )}
                      </>
                    )}
                  </div>
                </div>
                {/* Right: last encounter date + New Encounter button */}
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-xs text-clinical-muted">{fmtDate(p.lastDate)}</span>
                  <button
                    onClick={e => {
                      e.stopPropagation();
                      navigate(`/patient/${p.patientId}`, { state: { openNewEncounter: true } });
                    }}
                    className="btn-primary text-xs py-1.5 px-3"
                  >
                    New Encounter
                  </button>
                </div>
              </div>
            ))}

            {/* New Patient card */}
            <button
              onClick={() => setShowModal(true)}
              className="w-full border border-dashed border-clinical-accent/40 rounded-lg px-5 py-4 text-left bg-clinical-accent/5 hover:bg-clinical-accent/10 hover:border-clinical-accent/70 transition-colors flex items-center gap-3 mt-1"
            >
              <div className="w-7 h-7 rounded-md border border-clinical-accent/50 bg-clinical-accent/10 flex items-center justify-center text-clinical-accent text-base leading-none font-bold">+</div>
              <div>
                <div className="text-sm font-semibold text-clinical-accent">New Patient</div>
                <div className="text-xs text-clinical-text-dim">Register a new patient and start an encounter</div>
              </div>
            </button>
          </div>
        )}
      </main>

      {showModal && <NewPatientModal onClose={() => setShowModal(false)} onCreated={handleCreated} />}
    </div>
  );
}
