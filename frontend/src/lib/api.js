import axios from 'axios';

/**
 * Resolve the API base URL at RUNTIME (not build time).
 *
 * Why: create-react-app inlines `process.env.REACT_APP_BACKEND_URL` at build
 * time. When the school's Main Server serves the prebuilt bundle from
 * `python -m http.server 3000 --directory build`, that inlined value is
 * whatever the developer/CI used at build time (e.g. the Emergent preview
 * URL) - which does not resolve on the school's LAN. The runtime `.env`
 * the installer writes at `C:\balaji-fee\frontend\.env` is IGNORED by CRA
 * for a prebuilt bundle.
 *
 * Resolution order:
 *   1. LAN pattern: if the page is served from port 3000 (the pattern the
 *      Main Server + Client PCs always use), backend is on the SAME host
 *      + port 8001. Works for both `127.0.0.1:3000` (Main Server) and
 *      `192.168.x.x:3000` (Client PC).
 *   2. Build-time env var: preserves the Emergent preview environment where
 *      ingress routes `/api` on the same origin.
 *   3. Same-origin fallback.
 */
function detectApiBase() {
  if (typeof window !== 'undefined' && window.location) {
    const loc = window.location;
    // LAN mode: the Main-Server-style deployment serves the app on :3000.
    if (loc.port === '3000') {
      return `${loc.protocol}//${loc.hostname}:8001`;
    }
  }
  if (process.env.REACT_APP_BACKEND_URL) {
    return process.env.REACT_APP_BACKEND_URL;
  }
  if (typeof window !== 'undefined' && window.location) {
    return window.location.origin;
  }
  return '';
}

const API_BASE = detectApiBase();
const API = `${API_BASE}/api`;

// One-line safe boot log so the resolved API base is auditable from the
// Electron devtools console without ever leaking credentials or tokens.
try {
  // eslint-disable-next-line no-console
  console.info('[BalajiFeeHub] api base resolved  =>', API_BASE, '(source: ' +
    (typeof window !== 'undefined' && window.location && window.location.port === '3000'
      ? 'LAN runtime detection'
      : (process.env.REACT_APP_BACKEND_URL ? 'REACT_APP_BACKEND_URL build-time' : 'same-origin fallback')) + ')');
} catch (_) {}

const api = axios.create({ baseURL: API, withCredentials: true });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('bc_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401 && window.location.pathname !== '/login') {
      localStorage.removeItem('bc_token');
      window.location.href = '/login';
    }
    return Promise.reject(err);
  }
);

export default api;
export { API, API_BASE };
