import React, { createContext, useContext, useEffect, useState } from 'react';
import api from '@/lib/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [locked, setLockedState] = useState(false);

  useEffect(() => {
    const load = async () => {
      const token = localStorage.getItem('bc_token');
      if (!token) { setLoading(false); return; }
      try {
        const { data } = await api.get('/auth/me');
        setUser(data);
        if (localStorage.getItem('bc_locked') === '1') setLockedState(true);
      } catch (e) { localStorage.removeItem('bc_token'); }
      setLoading(false);
    };
    load();
  }, []);

  const login = async (email, password) => {
    // Safe diagnostic logging - never logs password or token.
    try {
      const { API_BASE } = await import('@/lib/api');
      // eslint-disable-next-line no-console
      console.info('[BalajiFeeHub] POST', `${API_BASE}/api/auth/login`, '(email:', email, ')');
    } catch (_) {}
    let data;
    try {
      const resp = await api.post('/auth/login', { email, password });
      data = resp.data;
      // eslint-disable-next-line no-console
      console.info('[BalajiFeeHub] login status:', resp.status, 'has_token:', !!data?.token, 'user_role:', data?.user?.role);
    } catch (err) {
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      // eslint-disable-next-line no-console
      console.warn('[BalajiFeeHub] login FAILED status:', status, 'detail:', typeof detail === 'string' ? detail : '(non-string body)', 'url:', err?.config?.baseURL + err?.config?.url);
      throw err;
    }
    if (!data || !data.token || !data.user) {
      // eslint-disable-next-line no-console
      console.warn('[BalajiFeeHub] login response missing token/user - keys received:', data ? Object.keys(data) : '(no body)');
      const shim = new Error('Server response is missing expected token/user fields');
      shim.response = { status: 200, data: { detail: 'Server response is missing expected token/user fields' } };
      throw shim;
    }
    localStorage.setItem('bc_token', data.token);
    localStorage.removeItem('bc_locked');
    setLockedState(false);
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    try { await api.post('/auth/logout'); } catch (e) {}
    localStorage.removeItem('bc_token');
    localStorage.removeItem('bc_locked');
    setLockedState(false);
    setUser(null);
  };

  const lock = () => { localStorage.setItem('bc_locked', '1'); setLockedState(true); };
  const unlock = () => { localStorage.removeItem('bc_locked'); setLockedState(false); };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, setUser, locked, lock, unlock }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => useContext(AuthContext);
