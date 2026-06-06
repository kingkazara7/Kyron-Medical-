import { useState, useEffect } from 'react';
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
            <div><label className="label">First Name</label><input className="input" value={form.first_name} onChange={e => setForm(f=>({...f,first_name:e.target.value}))} required /></div>
            <div><label className="label">Last Name</label><input className="input" value={form.last_name} onChange={e => setForm(f=>({...f,last_name:e.target.value}))} required /></div>
            <div><label className="label">Email</label><input type="email" className="input" value={form.email} onChange={e => setForm(f=>({...f,email:e.target.value}))} required /></div>
            <div><label className="label">Password</label><input type="password" className="input" value={form.password} onChange={e => setForm(f=>({...f,password:e.target.value}))} required /></div>
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
            <div><label className="label">Template Name</label><input className="input" value={form.name} onChange={e => setForm(f=>({...f,name:e.target.value}))} /></div>
            <div><label className="label">System Prompt</label><textarea className="input resize-none" rows={6} value={form.system_prompt} onChange={e => setForm(f=>({...f,system_prompt:e.target.value}))} /></div>
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

function EncountersTab() {
  const [encounters, setEncounters] = useState([]);
  const [providers, setProviders] = useState([]);
  const [filterId, setFilterId] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const navigate = useNavigate();

  const load = () => {
    const params = {};
    if (filterId) params.provider_id = filterId;
    if (dateFrom) params.date_from = dateFrom;
    if (dateTo) params.date_to = dateTo;
    api.get('/admin/encounters', { params }).then(r => setEncounters(r.data));
  };

  useEffect(() => {
    api.get('/admin/providers').then(r => setProviders(r.data));
    load();
  }, []);

  return (
    <div>
      <div className="flex gap-2 mb-4 flex-wrap">
        <select className="input w-auto text-xs" value={filterId} onChange={e => setFilterId(e.target.value)}>
          <option value="">All providers</option>
          {providers.filter(p => p.role === 'provider').map(p => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
        <input type="date" className="input w-auto text-xs" value={dateFrom} onChange={e => setDateFrom(e.target.value)} />
        <input type="date" className="input w-auto text-xs" value={dateTo} onChange={e => setDateTo(e.target.value)} />
        <button onClick={load} className="btn-primary text-xs">Filter</button>
      </div>

      <div className="space-y-1">
        {encounters.map(e => (
          <div key={e.encounter_id} className="card p-3 flex items-center justify-between text-sm">
            <div>
              <span className="font-medium">{e.patient_name}</span>
              <span className="text-clinical-muted text-xs ml-2">via {e.provider_name}</span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-clinical-muted">{new Date(e.created_at).toLocaleDateString()}</span>
              <span className={`tag text-xs ${e.status === 'saved' ? 'bg-clinical-success/10 text-clinical-success' : 'bg-clinical-warning/10 text-clinical-warning'}`}>{e.status}</span>
              {e.version_count > 0 && <span className="text-xs text-clinical-muted">v{e.version_count}</span>}
            </div>
          </div>
        ))}
        {encounters.length === 0 && <div className="text-clinical-muted text-sm text-center py-8">No encounters</div>}
      </div>
    </div>
  );
}

export default function AdminDashboard() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState('providers');

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
          <span className="text-clinical-muted text-xs">/ Admin</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => navigate('/')} className="btn-ghost text-xs">Provider View</button>
          <button onClick={logout} className="btn-ghost text-xs">Sign out</button>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-6">
        <div className="flex border-b border-clinical-border mb-6">
          <Tab active={tab === 'providers'} onClick={() => setTab('providers')}>Providers</Tab>
          <Tab active={tab === 'templates'} onClick={() => setTab('templates')}>Note Templates</Tab>
          <Tab active={tab === 'encounters'} onClick={() => setTab('encounters')}>All Encounters</Tab>
        </div>

        {tab === 'providers' && <ProvidersTab />}
        {tab === 'templates' && <TemplatesTab />}
        {tab === 'encounters' && <EncountersTab />}
      </main>
    </div>
  );
}
