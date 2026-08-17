import React, { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Loader2, Eye, EyeOff } from 'lucide-react';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const nav = useNavigate();

  const submit = async (e) => {
    e.preventDefault(); setErr(''); setLoading(true);
    try { await login(email, password); nav('/'); }
    catch (e) {
      const d = e?.response?.data?.detail;
      setErr(typeof d === 'string' ? d : 'Invalid email or password');
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-2">
      <div className="hidden lg:block relative">
        <img
          src="/login-bg.png"
          alt="Balaji Convent"
          className="w-full h-full object-cover"
        />
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
            <input
              data-testid="login-email"
              type="email" value={email} onChange={(e)=>setEmail(e.target.value)} required
              className="mt-1 w-full h-10 px-3 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-blue-600"
            />
          </div>
          <div>
            <label className="text-xs tracking-wide uppercase text-slate-600 font-medium">Password</label>
            <div className="mt-1 relative">
              <input
                data-testid="login-password"
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e)=>setPassword(e.target.value)}
                required
                className="w-full h-10 px-3 pr-10 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-blue-600"
              />
              <button
                type="button"
                tabIndex={-1}
                aria-label={showPassword ? 'Hide password' : 'Show password'}
                onClick={() => setShowPassword(v => !v)}
                className="absolute inset-y-0 right-0 w-10 flex items-center justify-center text-slate-500 hover:text-slate-800"
                data-testid="login-password-toggle"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          {err && <div data-testid="login-error" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{err}</div>}
          <button
            data-testid="login-submit"
            type="submit" disabled={loading}
            className="w-full h-10 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded transition-colors duration-150 disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />} Sign in
          </button>
        </form>
      </div>
    </div>
  );
}
