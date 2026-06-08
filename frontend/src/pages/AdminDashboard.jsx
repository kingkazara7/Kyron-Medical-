import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import api from '../api';

function Tab({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${active ? 'border-clinical-accent text-clinical-text' : 'border-transparent text-clinical-muted hover:text-clinical-text'}`}
    >
      {children}
    </button>
  );
}

// ── Read-only note modal ───────────────────────────────────────────────────
function NoteModal({ data, onClose }) {
  const versions = data.versions || [];
  const [activeVer, setActiveVer] = useState(
    versions.length > 0 ? versions[versions.length - 1].version_no : null
  );
  const version = versions.find(v => v.version_no === activeVer);
  const content = version ? version.content || {} : {};
  const { __label, _transcript, _label, ...soap } = content;
  const icdCodes = soap.icd10_codes || [];

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-clinical-surface border border-clinical-border rounded-xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl">
        {/* Header */}
        <div className="px-5 py-4 border-b border-clinical-border flex items-start justify-between shrink-0">
          <div>
            <div className="font-semibold text-sm text-clinical-text">{data.patient_name}</div>
            <div className="text-xs text-clinical-muted mt-0.5">
              via {data.provider_name} &middot;{' '}
              {new Date(data.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })} &middot;{' '}
              <span className={data.status === 'saved' ? 'text-clinical-success' : 'text-clinical-warning'}>
                {data.status}
              </span>
            </div>
          </div>
          <button onClick={onClose} className="text-clinical-muted hover:text-clinical-text text-lg leading-none ml-4">
            &times;
          </button>
        </div>

        {/* Version tabs */}
        {versions.length > 0 && (
          <div className="px-5 pt-3 flex gap-1.5 flex-wrap shrink-0">
            {versions.map(v => {
              const label = v.content && v.content.__label ? ` · ${v.content.__label}` : '';
              return (
                <button
                  key={v.version_no}
                  onClick={() => setActiveVer(v.version_no)}
                  className={`text-xs px-2.5 py-1 rounded border transition-colors ${
                    activeVer === v.version_no
                      ? 'border-clinical-accent bg-clinical-accent/10 text-clinical-accent'
                      : 'border-clinical-border text-clinical-muted hover:border-clinical-accent/40'
                  }`}
                >
                  v{v.version_no}{label}
                </button>
              );
            })}
          </div>
        )}

        {/* Content */}
        <div className="overflow-y-auto px-5 py-4 space-y-4 flex-1">
          {version ? (
            <>
              {[
                { key: 'subjective', label: 'Subjective' },
                { key: 'objective',  label: 'Objective' },
                { key: 'assessment', label: 'Assessment' },
                { key: 'plan',       label: 'Plan' },
              ].map(({ key, label }) => (
                <div key={key}>
                  <div className="text-xs font-semibold text-clinical-text-dim uppercase tracking-wider mb-1.5">
                    {label}
                  </div>
                  <div className="text-sm text-clinical-text bg-clinical-bg rounded-lg p-3 whitespace-pre-wrap leading-relaxed border border-clinical-border/50">
                    {soap[key] || '—'}
                  </div>
                </div>
              ))}
              {icdCodes.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-clinical-text-dim uppercase tracking-wider mb-2">
                    ICD-10 Codes
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {icdCodes.map((c, i) => (
                      <span
                        key={i}
                        className="text-xs px-2 py-1 rounded border border-clinical-accent/30 bg-clinical-accent/5 text-clinical-accent"
                      >
                        {c.code} — {c.description}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              <div className="text-xs text-clinical-muted pt-1">
                Saved {new Date(version.saved_at).toLocaleString()} by {version.saved_by_name}
              </div>
            </>
          ) : (
            <div className="text-clinical-muted text-sm py-4 text-center">
              No saved note for this encounter.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Providers tab ─────────────────────────────────────────────────────────
function ProvidersTab() {
  const [providers, setProviders] = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ first_name: '', last_name: '', email: '', password: '' });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = () => api.get('/admin/providers').then(r => setProviders(r.data));
  useEffect(() => { load(); }, []);

  const handleCreate = async e => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      await api.post('/admin/providers', form);
      setShowForm(false);
      setForm({ first_name: '', last_name: '', email: '', password: '' });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed');
    } finally { setLoading(false); }
  };

  const toggle = async (p) => {
    const action = p.is_active ? 'deactivate' : 'activate';
    await api.patch(`/admin/providers/${p.id}/${action}`);
    load();
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <span className="text-sm text-clinical-muted">{providers.length} providers</span>
        <button onClick={() => setShowForm(v => !v)} className="btn-primary text-xs">+ Add Provider</button>
      </div>
      {showForm && (
        <div className="card p-4 mb-4">
          <form onSubmit={handleCreate} className="grid grid-cols-2 gap-3">
            <div><label className="label">First Name</label><input className="input" value={form.first_name} onChange={e => setForm(f => ({...f, first_name: e.target.value}))} required /></div>
            <div><label className="label">Last Name</label><input className="input" value={form.last_name} onChange={e => setForm(f => ({...f, last_name: e.target.value}))} required /></div>
            <div><label className="label">Email</label><input type="email" className="input" value={form.email} onChange={e => setForm(f => ({...f, email: e.target.value}))} required /></div>
            <div><label className="label">Password</label><input type="password" className="input" value={form.password} onChange={e => setForm(f => ({...f, password: e.target.value}))} required /></div>
            {error && <div className="col-span-2 text-clinical-danger text-sm">{error}</div>}
            <div className="col-span-2 flex gap-2">
              <button type="button" onClick={() => setShowForm(false)} className="btn-ghost">Cancel</button>
              <button type="submit" disabled={loading} className="btn-primary">{loading ? 'Creating…' : 'Create'}</button>
            </div>
          </form>
        </div>
      )}
      <div className="space-y-2">
        {providers.map(p => (
          <div key={p.id} className="card p-3 flex items-center justify-between">
            <div>
              <div className="text-sm font-medium">{p.name}</div>
              <div className="text-xs text-clinical-muted">{p.email} · {p.role}</div>
            </div>
            <div className="flex items-center gap-2">
              <span className={`tag text-xs ${p.is_active ? 'bg-clinical-success/10 text-clinical-success' : 'bg-clinical-muted/10 text-clinical-muted'}`}>
                {p.is_active ? 'Active' : 'Inactive'}
              </span>
              {p.role !== 'admin' && (
                <button onClick={() => toggle(p)} className={p.is_active ? 'btn-danger' : 'btn-ghost text-xs'}>
                  {p.is_active ? 'Deactivate' : 'Activate'}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Templates tab ─────────────────────────────────────────────────────────
function TemplatesTab() {
  const [templates, setTemplates] = useState([]);
  const [editing, setEditing] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ name: '', system_prompt: '' });
  const [saving, setSaving] = useState(false);

  const load = () => api.get('/admin/templates').then(r => setTemplates(r.data));
  useEffect(() => { load(); }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      if (editing) {
        await api.put(`/admin/templates/${editing}`, form);
      } else {
        await api.post('/admin/templates', form);
      }
      setEditing(null);
      setShowForm(false);
      setForm({ name: '', system_prompt: '' });
      load();
    } finally { setSaving(false); }
  };

  const startEdit = (t) => {
    setForm({ name: t.name, system_prompt: t.system_prompt });
    setEditing(t.id);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!confirm('Delete this template?')) return;
    await api.delete(`/admin/templates/${id}`);
    load();
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <span className="text-sm text-clinical-muted">{templates.length} templates — changes take effect immediately on next generation</span>
        <button onClick={() => { setEditing(null); setForm({ name: '', system_prompt: '' }); setShowForm(v => !v); }} className="btn-primary text-xs">+ New Template</button>
      </div>
      {showForm && (
        <div className="card p-4 mb-4">
          <div className="space-y-3">
            <div><label className="label">Template Name</label><input className="input" value={form.name} onChange={e => setForm(f => ({...f, name: e.target.value}))} /></div>
            <div><label className="label">System Prompt</label><textarea className="input resize-none" rows={6} value={form.system_prompt} onChange={e => setForm(f => ({...f, system_prompt: e.target.value}))} /></div>
            <div className="flex gap-2">
              <button onClick={() => setShowForm(false)} className="btn-ghost">Cancel</button>
              <button onClick={handleSave} disabled={saving} className="btn-primary">{saving ? 'Saving…' : editing ? 'Update Template' : 'Create Template'}</button>
            </div>
          </div>
        </div>
      )}
      <div className="space-y-2">
        {templates.map(t => (
          <div key={t.id} className="card p-3">
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium">{t.name}</div>
                <div className="text-xs text-clinical-muted mt-1 line-clamp-2">{t.system_prompt}</div>
                <div className="text-xs text-clinical-muted mt-1">Updated {new Date(t.updated_at).toLocaleString()}</div>
              </div>
              <div className="flex items-center gap-2 ml-3 shrink-0">
                <button onClick={() => startEdit(t)} className="btn-ghost text-xs">Edit</button>
                <button onClick={() => handleDelete(t.id)} className="btn-danger text-xs">Delete</button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Encounters tab (two levels: patient list → /patient/:id with adminView) ──────
function EncountersTab() {
  const navigate = useNavigate();
  const [allEncounters, setAllEncounters] = useState([]);
  const [providers, setProviders] = useState([]);
  const [filterId, setFilterId] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  // Group encounters by patient
  const patients = useMemo(() => {
    const map = new Map();
    for (const enc of allEncounters) {
      if (!map.has(enc.patient_id)) {
        map.set(enc.patient_id, {
          patientId: enc.patient_id,
          patientName: enc.patient_name,
          encounters: [],
          providerSet: new Set(),
          latestDate: enc.updated_at || enc.created_at,
        });
      }
      const p = map.get(enc.patient_id);
      p.encounters.push(enc);
      p.providerSet.add(enc.provider_name);
      const d = enc.updated_at || enc.created_at;
      if (d > p.latestDate) p.latestDate = d;
    }
    return Array.from(map.values()).map(p => {
      const invalidCount   = p.encounters.filter(e => e.is_invalid).length;
      const draftCount     = p.encounters.filter(e =>
        (e.status === 'draft' || e.has_draft) && !e.is_invalid
      ).length;
      return {
        ...p,
        providers: Array.from(p.providerSet),
        invalidCount,
        draftCount,
      };
    });
  }, [allEncounters]);

  const doLoad = () => {
    const params = {};
    if (filterId) params.provider_id = filterId;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    api.get('/admin/encounters', { params }).then(r => setAllEncounters(r.data));
  };

  useEffect(() => {
    api.get('/admin/providers').then(r => setProviders(r.data));
    doLoad();
  }, []);

  return (
    <div>
      {/* Filter bar + legend */}
      <div className="flex gap-2 mb-5 flex-wrap items-center justify-between">
        <div className="flex gap-2 flex-wrap items-center">
          <select
            className="input w-auto text-xs"
            value={filterId}
            onChange={e => setFilterId(e.target.value)}
          >
            <option value="">All providers</option>
            {providers.filter(p => p.role === 'provider').map(p => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
          <input type="date" className="input w-auto text-xs" value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
          <input type="date" className="input w-auto text-xs" value={dateTo} onChange={e => setDateTo(e.target.value)} />
          <button onClick={doLoad} className="btn-primary text-xs px-4">Filter</button>
        </div>
        {/* Legend */}
        <div className="flex items-center gap-4 text-xs text-clinical-muted">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-clinical-success inline-block" />
            Normal
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-clinical-warning inline-block" />
            In progress
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-clinical-danger inline-block" />
            Invalid
          </span>
        </div>
      </div>

      {patients.length === 0 ? (
        <div className="text-clinical-muted text-sm text-center py-10">No encounters found</div>
      ) : (
        <div className="space-y-2">
          {patients.map(p => (
            <div
              key={p.patientId}
              onClick={() => navigate(`/patient/${p.patientId}`, { state: { adminView: true } })}
              className="card px-5 py-3.5 grid items-center cursor-pointer hover:border-clinical-accent/40 transition-colors"
            style={{ gridTemplateColumns: '1fr 7rem 6.5rem 11rem 5rem' }}
            >
              {/* Patient name */}
              <span className="font-semibold text-sm text-white truncate pr-4">{p.patientName}</span>
              {/* Encounter count */}
              <span className="text-xs text-clinical-muted">
                {p.encounters.length} encounter{p.encounters.length !== 1 ? 's' : ''}
              </span>
              {/* Date */}
              <span className="text-xs text-clinical-muted">
                {new Date(p.latestDate).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
              </span>
              {/* last edit by */}
              <span className="text-xs text-clinical-text truncate">
                <span className="text-clinical-muted">last edit by: </span>{p.providers.join(', ')}
              </span>
              {/* Status dots — color + count only; legend shown above */}
              <div className="flex items-center gap-2 justify-end">
                {p.invalidCount === 0 && p.draftCount === 0 ? (
                  <span className="w-2.5 h-2.5 rounded-full bg-clinical-success" title="Normal" />
                ) : (
                  <>
                    {p.invalidCount > 0 && (
                      <span className="flex items-center gap-1 text-xs text-clinical-danger" title={`${p.invalidCount} invalid`}>
                        <span className="w-2.5 h-2.5 rounded-full bg-clinical-danger shrink-0" />
                        {p.invalidCount}
                      </span>
                    )}
                    {p.draftCount > 0 && (
                      <span className="flex items-center gap-1 text-xs text-clinical-warning" title={`${p.draftCount} in progress`}>
                        <span className="w-2.5 h-2.5 rounded-full bg-clinical-warning shrink-0" />
                        {p.draftCount}
                      </span>
                    )}
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main AdminDashboard ───────────────────────────────────────────────────
export default function AdminDashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState(
    () => sessionStorage.getItem('adminTab') || 'providers'
  );
  // Persist active tab so navigating away and back restores the same tab
  const changeTab = (t) => { sessionStorage.setItem('adminTab', t); setTab(t); };

  return (
    <div className="min-h-screen bg-clinical-bg">
      <header className="border-b border-clinical-border bg-clinical-surface px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-semibold text-sm text-white">Admin: <span className="font-normal">{user?.name}</span></span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={logout} className="text-xs border border-clinical-danger text-clinical-danger hover:bg-clinical-danger/10 px-3 py-1.5 rounded transition-colors">Sign out</button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-6">
        <div className="flex border-b border-clinical-border mb-6">
          <Tab active={tab === 'providers'} onClick={() => changeTab('providers')}>Providers</Tab>
          <Tab active={tab === 'templates'} onClick={() => changeTab('templates')}>Note Templates</Tab>
          <Tab active={tab === 'encounters'} onClick={() => changeTab('encounters')}>All Patients</Tab>
        </div>

        {tab === 'providers' && <ProvidersTab />}
        {tab === 'templates' && <TemplatesTab />}
        {tab === 'encounters' && <EncountersTab />}
      </main>
    </div>
  );
}
