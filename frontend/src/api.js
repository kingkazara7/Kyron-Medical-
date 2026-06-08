import axios from 'axios';

const api = axios.create({ baseURL: '/api' });

api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token');
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

api.interceptors.response.use(
  r => r,
  err => {
    if (err.response?.status === 401) {
      const current = window.location.pathname + window.location.search;
      const detail = err.response?.data?.detail || '';
      const isSuperseded = detail.includes('superseded');
      const event = isSuperseded ? 'kyron:session-superseded' : 'kyron:session-expired';
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      if (/^\/encounter\//.test(window.location.pathname)) {
        sessionStorage.setItem('redirectAfterLogin', current);
        window.dispatchEvent(new CustomEvent(event));
      } else {
        if (current !== '/login') {
          sessionStorage.setItem('redirectAfterLogin', current);
        }
        const reason = isSuperseded ? 'superseded' : 'expired';
        window.location.href = `/login?reason=${reason}`;
      }
    } else if (
      err.response?.status === 403 &&
      err.response?.data?.detail === 'Account deactivated'
    ) {
      // Account was deactivated while session was active.
      // Clear auth state but do NOT redirect away from the workspace —
      // the provider may have unsaved note content that must remain visible.
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.dispatchEvent(new CustomEvent('kyron:account-deactivated'));
      // Only redirect if not on a workspace page (no draft content to preserve)
      if (!/^\/encounter\//.test(window.location.pathname)) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(err);
  }
);

export default api;
