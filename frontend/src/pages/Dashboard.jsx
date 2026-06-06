import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import api from '../api';

function NewEncounterModal({ onClose, onCreated }) {
  const [form, setForm] = useState({ first_name: '', last_name: '', dob: '', template_id: '' });
  const [templates, setTemplates] = useState([]);
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
        patient: { first_name: form.first_name, last_name: form.last_name, dob: form.dob },
        template_id: form.template_id ? parseInt(form.template_id) : null,
      });
      onCreated(data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create encounter');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="card w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold">New Encounter</h2>
          <button onClick={onClose} className="text-clinical-muted hover:text-clinical-text">✕</button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">First Name</label>
              <input className="input" value={form.first_name} onChange={e => setForm(f => ({...f, first_name: e.target.value}))} required />
            </div>
            <div>
              <label className="label">Last Name</label>
              <input className="input" value={form.last_name} onChange={e => setForm(f => ({...f, last_name: e.target.value}))} required />
            </div>
          </div>
          <div>
            <label className="label">Date of Birth</label>
            <input type="date" className="input" value={form.dob} onChange={e => setForm(f => ({...f, dob: e.target.value}))} required />
          </div>
          <div>
            <label className="label">Template (optional)</label>
            <select className="input" value={form.template_id} onChange={e => setForm(f => ({...f, template_id: e.target.value}))}>
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

export default function Dashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [encounters, setEncounters] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/encounters').then(r => setEncounters(r.data)).finally(() => setLoading(false));
  }, []);

  const handleCreated = data => {
    setShowModal(false);
    navigate(`/encounter/${data.encounter_id}`);
  };

  return (
    <div className="min-h-screen bg-clinical-bg">
      <header className="border-b border-clinical-border bg-clinical-surface px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-6 h-6 bg-clinical-accent rounded flex items-center justify-center">
            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <span className="font-semibold text-sm">Kyron Scribe</span>
          <span className="text-clinical-muted text-xs">/ Encounters</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-clinical-text-dim">{user?.name}</span>
          {user?.role === 'admin' && (
            <button onClick={() => navigate('/admin')} className="btn-ghost text-xs">Admin</button>
          )}
          <button onClick={logout} className="btn-ghost text-xs">Sign out</button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-lg font-semibold">Encounters</h1>
          <button onClick={() => setShowModal(true)} className="btn-primary flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            New Encounter
          </button>
        </div>

        {loading ? (
          <div className="text-clinical-muted text-sm text-center py-12">Loading…</div>
        ) : encounters.length === 0 ? (
          <div className="card p-12 text-center">
            <div className="text-clinical-muted text-sm mb-3">No encounters yet</div>
            <button onClick={() => setShowModal(true)} className="btn-primary">Start your first encounter</button>
          </div>
        ) : (
          <div className="space-y-2">
            {encounters.map(e => (
              <button
                key={e.encounter_id}
                onClick={() => navigate(`/encounter/${e.encounter_id}`)}
                className="card w-full p-4 text-left hover:border-clinical-accent/50 transition-colors flex items-center justify-between group"
              >
                <div>
                  <div className="font-medium text-sm">{e.patient_name}</div>
                  <div className="text-xs text-clinical-muted mt-0.5">
                    {new Date(e.created_at).toLocaleDateString('en-US', {month:'short',day:'numeric',year:'numeric',hour:'2-digit',minute:'2-digit'})}
                    {e.version_count > 0 && ` · v${e.version_count}`}
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`tag ${e.status === 'saved' ? 'bg-clinical-success/10 text-clinical-success' : 'bg-clinical-warning/10 text-clinical-warning'}`}>
                    {e.status}
                  </span>
                  <svg className="w-4 h-4 text-clinical-muted group-hover:text-clinical-text transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </div>
              </button>
            ))}
          </div>
        )}
      </main>

      {showModal && <NewEncounterModal onClose={() => setShowModal(false)} onCreated={handleCreated} />}
    </div>
  );
}
