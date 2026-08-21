import React, { useState, useEffect } from 'react';
import { useAuth } from '@/context/AuthContext';
import { API_BASE } from '@/lib/api';
import { useNavigate } from 'react-router-dom';
import { Loader2, Eye, EyeOff, Info } from 'lucide-react';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [err, setErr] = useState('');
  const [diag, setDiag] = useState(null);
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const nav = useNavigate();

  useEffect(() => {
    // Baseline diagnostic shown before any login attempt.
    setDiag({
      stage: 'idle',
      api_base: API_BASE,
      endpoint: `${API_BASE}/api/auth/login`,
      served_from: typeof window !== 'undefined' ? window.location.href : '(no window)',
      served_host: typeof window !== 'undefined' ? window.location.hostname : '(n/a)',
      served_port: typeof window !== 'undefined' ? (window.location.port || '(none)') : '(n/a)',
    });
  }, []);

  const submit = async (e) => {
    e.preventDefault(); setErr(''); setLoading(true);
    const t0 = performance.now();
    try {
      const user = await login(email, password);
      const t1 = performance.now();
      setDiag((d) => ({ ...d, stage: 'success', http_status: 200, response_keys: 'token,user', role: user?.role, latency_ms: Math.round(t1 - t0), token_stored: !!localStorage.getItem('bc_token') }));
      nav('/');
    } catch (e) {
      const t1 = performance.now();
      const status = e?.response?.status ?? null;
      const detail = e?.response?.data?.detail;
      const keys = e?.response?.data ? Object.keys(e.response.data).join(',') : '(no body)';
      const errMsg = e?.message || 'unknown';
      const network = !e?.response;
      setErr(typeof detail === 'string' ? detail : (network ? `Network error: ${errMsg}` : `HTTP ${status ?? '???'} - ${errMsg}`));
      setDiag((d) => ({ ...d, stage: 'failed', http_status: status, response_keys: keys, response_detail: typeof detail === 'string' ? detail : '(non-string)', network_error: network, error_message: errMsg, latency_ms: Math.round(t1 - t0), token_stored: !!localStorage.getItem('bc_token') }));
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:block relative">
        <img src="/login-bg.png" alt="Balaji Convent" className="w-full h-full object-cover" />
        <div className="absolute inset-0 bg-slate-900/55" />
        <div className="absolute bottom-10 left-10 right-10 text-white">
          <div className="text-xs tracking-[0.3em] uppercase text-slate-300 mb-3">Balaji Convent &amp; Junior College · Butibori, Nagpur</div>
          <div className="font-heading text-4xl font-semibold leading-tight mb-3">Balaji FeeHub</div>
          <div className="text-slate-300 text-sm max-w-md">Fee Management System · Offline-capable · Auditable · Precise.</div>
        </div>
      </div>
      <div className="flex items-center justify-center p-8 bg-white">
        <form onSubmit={submit} className="w-full max-w-sm space-y-5" data-testid="login-form">
          <div className="flex items-center gap-3 mb-2">
            <img src="/school-logo.jpeg" alt="Balaji Convent logo" className="w-14 h-14 rounded-full object-cover ring-1 ring-slate-200" data-testid="login-logo" />
            <div>
              <div className="font-heading font-bold text-xl leading-tight" data-testid="login-app-name">Balaji FeeHub</div>
              <div className="text-[11px] tracking-widest uppercase text-slate-500 leading-tight">Fee Management System</div>
              <div className="text-[10px] tracking-wider uppercase text-slate-400 leading-tight">Version 1.0</div>
            </div>
          </div>
          <div className="border-t border-slate-100 pt-4">
            <div className="text-[10px] tracking-[0.25em] uppercase text-slate-500 font-semibold leading-tight" data-testid="login-school-name">Balaji Convent &amp; Junior College</div>
            <div className="text-[10px] tracking-[0.25em] uppercase text-slate-400 leading-tight">Butibori, Nagpur</div>
          </div>
          <div>
            <h2 className="font-heading text-2xl font-semibold text-slate-900 tracking-tight">Sign in</h2>
            <p className="text-sm text-slate-500 mt-1">Enter your credentials to access the accounting workstation.</p>
          </div>
          <div>
            <label className="text-xs tracking-wide uppercase text-slate-600 font-medium">Email</label>
            <input data-testid="login-email" type="email" value={email} onChange={(e)=>setEmail(e.target.value)} required autoComplete="username"
              className="mt-1 w-full h-10 px-3 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-blue-600" />
          </div>
          <div>
            <label className="text-xs tracking-wide uppercase text-slate-600 font-medium">Password</label>
            <div className="mt-1 relative">
              <input data-testid="login-password" type={showPassword ? 'text' : 'password'} value={password} onChange={(e)=>setPassword(e.target.value)} required autoComplete="current-password"
                className="w-full h-10 px-3 pr-10 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-blue-600" />
              <button type="button" tabIndex={-1} aria-label={showPassword ? 'Hide password' : 'Show password'} onClick={() => setShowPassword(v => !v)}
                className="absolute inset-y-0 right-0 w-10 flex items-center justify-center text-slate-500 hover:text-slate-800" data-testid="login-password-toggle">
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          {err && <div data-testid="login-error" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{err}</div>}
          <button data-testid="login-submit" type="submit" disabled={loading}
            className="w-full h-10 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded transition-colors duration-150 disabled:opacity-60 flex items-center justify-center gap-2">
            {loading && <Loader2 className="w-4 h-4 animate-spin" />} Sign in
          </button>

          {diag && (
            <details data-testid="login-diagnostics" className="mt-3 rounded border border-slate-200 bg-slate-50 text-[11px] font-mono text-slate-700" open={diag.stage === 'failed'}>
              <summary className="cursor-pointer px-3 py-2 flex items-center gap-1.5 text-slate-600 font-sans font-medium text-xs">
                <Info className="w-3.5 h-3.5" /> Login diagnostics (click to {diag.stage === 'failed' ? 'hide' : 'show'})
              </summary>
              <div className="px-3 pb-3 space-y-0.5 leading-relaxed">
                <div><span className="text-slate-400">stage       :</span> {diag.stage}</div>
                <div><span className="text-slate-400">api_base    :</span> {diag.api_base || '(empty)'}</div>
                <div><span className="text-slate-400">endpoint    :</span> {diag.endpoint}</div>
                <div><span className="text-slate-400">served_from :</span> {diag.served_from}</div>
                <div><span className="text-slate-400">served_host :</span> {diag.served_host}:{diag.served_port}</div>
                {diag.stage !== 'idle' && <>
                  <div><span className="text-slate-400">http_status :</span> {String(diag.http_status)}</div>
                  <div><span className="text-slate-400">latency_ms  :</span> {diag.latency_ms}</div>
                  <div><span className="text-slate-400">resp_keys   :</span> {diag.response_keys}</div>
                  {diag.stage === 'failed' && <>
                    <div><span className="text-slate-400">resp_detail :</span> {diag.response_detail}</div>
                    <div><span className="text-slate-400">network_err :</span> {String(diag.network_error)}</div>
                    <div><span className="text-slate-400">err_message :</span> {diag.error_message}</div>
                  </>}
                  {diag.stage === 'success' && <>
                    <div><span className="text-slate-400">user_role   :</span> {diag.role}</div>
                    <div><span className="text-slate-400">token_saved :</span> {String(diag.token_stored)}</div>
                  </>}
                </>}
                <div className="text-slate-400 text-[10px] mt-1.5 pt-1.5 border-t border-slate-200">Passwords and tokens are never shown here.</div>
              </div>
            </details>
          )}
        </form>
      </div>
    </div>
  );
}
