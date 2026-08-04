import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';

const LOGO = "https://customer-assets-0z36b82j.emergentagent.net/job_finance-hub-school/artifacts/ce0kfh6k_schoolo%20logo.jpeg";
const inr = (n) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(n || 0);
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function StudentLookup() {
  const { adm } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');
  const [active, setActive] = useState(0);

  useEffect(() => {
    axios.get(`${API}/public/student-lookup/${adm}`)
      .then(r => setData(r.data))
      .catch(e => setErr(e?.response?.data?.detail || 'Student not found'));
  }, [adm]);

  if (err) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="max-w-md bg-white border border-slate-200 rounded p-8 text-center">
        <div className="text-red-700 text-lg font-semibold mb-2">Student Not Found</div>
        <div className="text-sm text-slate-500">Admission no. <span className="font-mono">{adm}</span> was not located.</div>
      </div>
    </div>
  );
  if (!data) return <div className="min-h-screen flex items-center justify-center text-sm text-slate-500">Loading…</div>;

  const children = data.children || [];
  const combined = data.combined;
  const current = children[active];

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="bg-slate-900 text-white px-6 py-4 flex items-center gap-3">
        <img src={LOGO} className="w-10 h-10 rounded-full object-cover" alt="logo" />
        <div>
          <div className="font-semibold text-[15px] tracking-tight">Balaji Convent & Junior College</div>
          <div className="text-[11px] text-slate-300 tracking-widest uppercase">Parent Lookup · View-Only</div>
        </div>
      </div>

      <div className="max-w-2xl mx-auto p-6 space-y-4">
        {children.length > 1 && (
          <div className="bg-emerald-50 border-2 border-emerald-500 rounded p-4">
            <div className="text-[11px] uppercase tracking-widest text-emerald-800 font-bold mb-1">Family Ledger · {children.length} children</div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div className="flex justify-between"><span className="text-slate-600">Combined Total Fee</span><span className="font-mono tabular font-semibold">{inr(combined.total_fee)}</span></div>
              <div className="flex justify-between"><span className="text-slate-600">Combined Paid</span><span className="font-mono tabular text-emerald-700 font-semibold">{inr(combined.paid)}</span></div>
              <div className="col-span-2 mt-1 pt-2 border-t border-emerald-200 flex justify-between"><span className="text-slate-600 font-bold">Combined Outstanding</span><span className={`font-mono tabular text-xl font-bold ${combined.outstanding > 0 ? 'text-red-700' : 'text-emerald-700'}`}>{inr(combined.outstanding)}</span></div>
            </div>
          </div>
        )}

        {children.length > 1 && (
          <div className="flex gap-2 flex-wrap">
            {children.map((c, i) => (
              <button key={c.student.admission_no} onClick={()=>setActive(i)} className={`px-3 py-2 rounded text-sm border ${i===active ? 'bg-slate-900 border-slate-900 text-white' : 'bg-white border-slate-300 hover:bg-slate-50'}`}>
                <div className="font-semibold">{c.student.name}</div>
                <div className="text-[10px] opacity-80 font-mono">{c.student.admission_no}</div>
              </button>
            ))}
          </div>
        )}

        {current && (
          <>
            <div className="bg-white border border-slate-200 rounded p-5">
              <div className="text-[11px] uppercase tracking-widest text-slate-500">Student</div>
              <div className="font-heading text-lg font-semibold">{current.student.name}</div>
              <div className="text-[13px] text-slate-500 font-mono">{current.student.admission_no}</div>
              {current.student.guardian_name && <div className="text-sm text-slate-600 mt-1">Guardian: {current.student.guardian_name} · <span className="font-mono">{current.student.guardian_mobile || '—'}</span></div>}
            </div>
            <div className="bg-white border border-slate-200 rounded p-5">
              <div className="text-[11px] uppercase tracking-widest text-slate-500 mb-3">Annual Ledger</div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div className="flex justify-between"><span className="text-slate-500">Total Fee</span><span className="font-mono tabular">{inr(current.ledger.total_fee)}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Paid</span><span className="font-mono tabular text-emerald-700">{inr(current.ledger.paid)}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Concession</span><span className="font-mono tabular">{inr(current.ledger.adjusted)}</span></div>
                <div className="flex justify-between"><span className="text-slate-500">Refunded</span><span className="font-mono tabular">{inr(current.ledger.refunded)}</span></div>
                <div className="col-span-2 mt-2 pt-2 border-t border-slate-200 flex justify-between">
                  <span className="text-slate-500">Outstanding</span>
                  <span className={`font-mono tabular text-lg font-bold ${current.ledger.outstanding > 0 ? 'text-red-700' : 'text-emerald-700'}`}>{inr(current.ledger.outstanding)}</span>
                </div>
              </div>
              {current.ledger.receipts.length > 0 && (
                <div className="mt-5">
                  <div className="text-[11px] uppercase tracking-widest text-slate-500 mb-2">Recent Receipts</div>
                  <div className="border border-slate-200 rounded overflow-hidden">
                    {current.ledger.receipts.map(x => (
                      <div key={x.number} className="px-3 py-2 border-b border-slate-100 last:border-0 flex justify-between items-center text-sm">
                        <div><div className="font-mono font-medium">{x.number}</div><div className="text-[11px] text-slate-500 capitalize">{x.type?.replace('_',' ')} · {new Date(x.date).toLocaleDateString('en-IN')}</div></div>
                        <div className="text-right"><div className="font-mono tabular font-semibold">{inr(x.total)}</div><div className="text-[10px] uppercase text-slate-500">{x.mode}</div></div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </>
        )}

        <div className="text-center text-[11px] text-slate-500 py-4">
          Balaji Convent & Junior College · Butibori, Nagpur · View-only. For queries visit the school office.
        </div>
      </div>
    </div>
  );
}
