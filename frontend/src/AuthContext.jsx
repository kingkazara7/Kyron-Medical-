import { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import api from './api';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try { return JSON.parse(localStorage.getItem('user')); } catch { return null; }
  });
  // AbortController for the long-lived SSE connection
  const streamAbortRef = useRef(null);

  // Open a persistent SSE connection to /api/auth/session-stream.
  // The server pushes two events when another device logs in:
  //   "flush"      — draft save while token is still valid
  //   "superseded" — session is now invalid; show overlay or redirect
  // The connection auto-reconnects on drop (network glitch, server restart, etc.)
  const startSessionStream = useCallback(() => {
    if (streamAbortRef.current) streamAbortRef.current.abort();
    const token = localStorage.getItem('token');
    if (!token) return;
    const controller = new AbortController();
    streamAbortRef.current = controller;

    fetch('/api/auth/session-stream', {
      headers: { Authorization: `Bearer ${token}` },
      signal: controller.signal,
    })
      .then(async res => {
        if (!res.ok) {
          // Connection rejected (401 already handled by server logic)
          scheduleReconnect();
          return;
        }
        const reader = res.body.getReader();
        const dec = new TextDecoder();
        let buf = '';
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          // Split on newlines; keep the last incomplete chunk in buf
          const lines = buf.split('\n');
          buf = lines.pop() ?? '';
          for (const line of lines) {
            if (!line.startsWith('data:')) continue;
            const data = line.slice(5).trim();
            if (data === 'flush') {
              // Phase 1: session about to be superseded — flush draft NOW
              // Token is still valid so the save will succeed
              window.dispatchEvent(new CustomEvent('kyron:session-flush'));
            } else if (data === 'superseded') {
              // Phase 2: session is now invalid
              const current = window.location.pathname + window.location.search;
              localStorage.removeItem('token');
              localStorage.removeItem('user');
              if (/^\/encounter\//.test(window.location.pathname)) {
                sessionStorage.setItem('redirectAfterLogin', current);
                window.dispatchEvent(new CustomEvent('kyron:session-superseded'));
              } else {
                if (current !== '/login') sessionStorage.setItem('redirectAfterLogin', current);
                window.location.href = '/login?reason=superseded';
              }
              return; // Stop — do not reconnect
            }
          }
        }
        // Stream closed cleanly (server restart, etc.) — reconnect
        scheduleReconnect();
      })
      .catch(err => {
        if (err.name === 'AbortError') return; // Intentional abort on logout
        scheduleReconnect();
      });

    function scheduleReconnect() {
      setTimeout(() => {
        if (localStorage.getItem('token')) startSessionStream();
      }, 3000);
    }
  }, []); // Stable reference — reads localStorage at call time

  const stopSessionStream = useCallback(() => {
    if (streamAbortRef.current) {
      streamAbortRef.current.abort();
      streamAbortRef.current = null;
    }
  }, []);

  // Resume stream on mount if already logged in (e.g. page refresh)
  useEffect(() => {
    if (user) startSessionStream();
    return () => stopSessionStream();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(async (email, password) => {
    // Tear down any pre-existing SSE stream FIRST. Otherwise the backend, while
    // processing this very login, would push "superseded" to our own still-open
    // connection — and that handler would wipe the brand-new token and bounce us
    // back to /login (self-supersession). Closing it now also makes the backend's
    // has_connections() check false, so it skips the flush/supersede dance.
    // Cross-device supersession is unaffected: that is a *different* browser's stream.
    stopSessionStream();
    const { data } = await api.post('/auth/login', { email, password });
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('user', JSON.stringify(data));
    setUser(data);
    startSessionStream(); // Begin listening for supersession events
    return data;
  }, [startSessionStream, stopSessionStream]);

  const logout = useCallback(() => {
    stopSessionStream();
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
  }, [stopSessionStream]);

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
