import React, { useState } from 'react';
import { useAuth } from '@/context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { School, Loader2 } from 'lucide-react';

export default function Login() {
  const [email, setEmail] = useState('neulkarprathamesh@gmail.com');
  const [password, setPassword] = useState('');
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
          src="https://images.unsplash.com/photo-1635424239131-32dc44986b56?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxNzV8MHwxfHNlYXJjaHwxfHxxdWlldCUyMGVtcHR5JTIwY2xhc3Nyb29tJTIwc3VubGlnaHR8ZW58MHx8fHwxNzg1ODE5NTA3fDA&ixlib=rb-4.1.0&q=85"
          alt="School"
          className="w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-slate-900/60" />
        <div className="absolute bottom-10 left-10 right-10 text-white">
          <div className="text-xs tracking-[0.3em] uppercase text-slate-300 mb-3">Est. Balaji Convent & Junior College</div>
          <div className="font-heading text-4xl font-semibold leading-tight mb-3">Fee & Financial Management</div>
          <div className="text-slate-300 text-sm max-w-md">A serious accounting workstation for cashiers, accountants and administrators. Offline-capable. Auditable. Precise.</div>
        </div>
      </div>
      <div className="flex items-center justify-center p-8 bg-white">
        <form onSubmit={submit} className="w-full max-w-sm space-y-5" data-testid="login-form">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded bg-blue-600 flex items-center justify-center text-white">
              <School className="w-5 h-5" strokeWidth={1.8} />
            </div>
            <div>
              <div className="font-heading font-semibold text-lg leading-tight">Balaji Convent</div>
              <div className="text-[11px] tracking-widest uppercase text-slate-500">Fee Software · v1.0</div>
            </div>
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
            <input
              data-testid="login-password"
              type="password" value={password} onChange={(e)=>setPassword(e.target.value)} required
              className="mt-1 w-full h-10 px-3 border border-slate-300 rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-600 focus:border-blue-600"
            />
          </div>
          {err && <div data-testid="login-error" className="text-sm text-red-600 bg-red-50 border border-red-200 rounded px-3 py-2">{err}</div>}
          <button
            data-testid="login-submit"
            type="submit" disabled={loading}
            className="w-full h-10 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded transition-colors duration-150 disabled:opacity-60 flex items-center justify-center gap-2"
          >
            {loading && <Loader2 className="w-4 h-4 animate-spin" />} Sign in
          </button>
          <div className="text-xs text-slate-500 border-t border-slate-200 pt-4">
            <div className="font-medium text-slate-700 mb-1">Demo accounts</div>
            <div>cashier@balaji.local / cashier123</div>
            <div>accountant@balaji.local / account123</div>
            <div>manager@balaji.local / manager123</div>
          </div>
        </form>
      </div>
    </div>
  );
}
