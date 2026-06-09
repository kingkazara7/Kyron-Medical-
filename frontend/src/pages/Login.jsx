import { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const reason = new URLSearchParams(location.search).get('reason');
  // The session banner (superseded/expired) is informational only. Dismiss it as
  // soon as the user starts a fresh login so it can't mask a real error (e.g. a
  // wrong password) or make the page look "stuck".
  const [showReason, setShowReason] = useState(true);

  const handleSubmit = async e => {
    e.preventDefault();
    setError('');
    setShowReason(false);
    setLoading(true);
    try {
      const user = await login(email, password);
      // Return provider to wherever they were when the session expired
      const redirect = sessionStorage.getItem('redirectAfterLogin');
      sessionStorage.removeItem('redirectAfterLogin');
      if (redirect && redirect !== '/login') {
        navigate(redirect, { replace: true });
      } else {
        navigate(user.role === 'admin' ? '/admin' : '/', { replace: true });
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-clinical-bg flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="inline-flex items-center gap-2 mb-3">
            <div className="w-8 h-8 bg-clinical-accent rounded flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <span className="text-lg font-semibold tracking-tight">Kyron Scribe</span>
          </div>
          <p className="text-clinical-text-dim text-sm">AI Clinical Documentation</p>
        </div>

        {/* Session expiry notification banners */}
        {reason === 'superseded' && showReason && (
          <div className="mb-4 px-4 py-3 rounded border border-clinical-warning/40 bg-clinical-warning/10 text-sm text-clinical-warning flex items-center gap-2">
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            <span>Your account was signed in on another device. Please log in again.</span>
          </div>
        )}
        {reason === 'expired' && showReason && (
          <div className="mb-4 px-4 py-3 rounded border border-clinical-accent/40 bg-clinical-accent/10 text-sm text-clinical-accent flex items-center gap-2">
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            <span>Your session has expired. Please log in again.</span>
          </div>
        )}

        <div className="card p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">Email</label>
              <input
                type="email"
                value={email}
                onChange={e => { setEmail(e.target.value); setShowReason(false); }}
                className="input"
                placeholder="sarah.chen@kyron.health"
                required
                autoFocus
              />
            </div>
            <div>
              <label className="label">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                className="input"
                placeholder="••••••••"
                required
              />
            </div>
            {error && (
              <div className="text-clinical-danger text-sm bg-clinical-danger/10 border border-clinical-danger/20 rounded px-3 py-2">
                {error}
              </div>
            )}
            <button type="submit" disabled={loading} className="btn-primary w-full justify-center flex">
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <div className="mt-4 pt-4 border-t border-clinical-border">
            <p className="text-xs text-clinical-muted mb-2">Demo accounts <span className="text-clinical-accent/60">(click to fill)</span>:</p>
            <div className="space-y-1">
              {[
                { label: "Admin", email: "admin@kyron.health", password: "Admin1234!" },
                { label: "Dr. Chen", email: "sarah.chen@kyron.health", password: "Provider1234!" },
                { label: "Dr. Rivera", email: "james.rivera@kyron.health", password: "Provider1234!" },
                { label: "Dr. Patel", email: "emily.patel@kyron.health", password: "Provider1234!" },
              ].map(acc => (
                <button
                  key={acc.email}
                  type="button"
                  onClick={() => { setEmail(acc.email); setPassword(acc.password); }}
                  className="w-full text-left px-2 py-1 rounded hover:bg-clinical-border/30 transition-colors"
                >
                  <span className="text-xs font-semibold text-clinical-text-dim w-16 inline-block">{acc.label}</span>
                  <span className="text-xs font-mono text-clinical-muted">{acc.email}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
