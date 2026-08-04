import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';

const LOGO = "https://customer-assets-0z36b82j.emergentagent.net/job_finance-hub-school/artifacts/ce0kfh6k_schoolo%20logo.jpeg";
const inr = (n) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(n || 0);
const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function Lookup() {
  const { number } = useParams();
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    axios.get(`${API}/public/lookup/${number}`)
      .then(r => setData(r.data))
      .catch(e => setErr(e?.response?.data?.detail || 'Receipt not found'));
  }, [number]);

  if (err) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="max-w-md bg-white border border-slate-200 rounded p-8 text-center">
        <div className="text-red-700 text-lg font-semibold mb-2">Receipt Not Found</div>
        <div className="text-sm text-slate-500">The receipt <span className="font-mono">{number}</span> could not be located. Please contact the school office.</div>
      </div>
    </div>
  );
  if (!data) return <div className="min-h-screen flex items-center justify-center text-sm text-slate-500">Loading…</div>;

  const r = data.receipt;
  const s = data.student;
  const l = data.ledger;

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
        <div className="bg-white border border-slate-200 rounded p-5">
          <div className="text-[11px] uppercase tracking-widest text-slate-500">Receipt</div>
          <div className="font-mono font-bold text-lg text-slate-900">{r.number}</div>
          <div className="grid grid-cols-2 gap-3 mt-3 text-sm">
            <div><span className="text-slate-500">Date: </span>{new Date(r.created_at).toLocaleString('en-IN')}</div>
            <div><span className="text-slate-500">Type: </span><span className="capitalize">{r.receipt_type?.replace('_',' ')}</span></div>
            <div><span className="text-slate-500">Amount: </span><span className="font-mono tabular font-semibold">{inr(r.total)}</span></div>
            <div><span className="text-slate-500">Mode: </span><span className="uppercase">{r.payment_mode}</span></div>
            <div className="col-span-2"><span className="text-slate-500">In words: </span><i>{r.amount_in_words}</i></div>
            {r.status === 'cancelled' && <div className="col-span-2 text-red-600 font-bold">*** CANCELLED — {r.cancel_reason || 'no reason'} ***</div>}
          </div>
        </div>

        {s && (
          <div className="bg-white border border-slate-200 rounded p-5">
            <div className="text-[11px] uppercase tracking-widest text-slate-500">Student</div>
            <div className="font-heading text-lg font-semibold">{s.name}</div>
            <div className="text-[13px] text-slate-500 font-mono">{s.admission_no}</div>
            {s.guardian_name && <div className="text-sm text-slate-600 mt-1">Guardian: {s.guardian_name} · <span className="font-mono">{s.guardian_mobile || '—'}</span></div>}
          </div>
        )}

        {l && (
          <div className="bg-white border border-slate-200 rounded p-5">
            <div className="text-[11px] uppercase tracking-widest text-slate-500 mb-3">Annual Ledger Summary</div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Row label="Total Fee" value={inr(l.total_fee)} />
              <Row label="Paid" value={inr(l.paid)} tone="text-emerald-700" />
              <Row label="Concession" value={inr(l.adjusted)} />
              <Row label="Refunded" value={inr(l.refunded)} />
              <div className="col-span-2 mt-2 pt-2 border-t border-slate-200">
                <Row label="Outstanding" value={inr(l.outstanding)} tone={l.outstanding > 0 ? "text-red-700 font-bold" : "text-emerald-700 font-bold"} bold />
              </div>
            </div>

            {l.receipts.length > 0 && (
              <div className="mt-5">
                <div className="text-[11px] uppercase tracking-widest text-slate-500 mb-2">Recent Receipts</div>
                <div className="border border-slate-200 rounded overflow-hidden">
                  {l.receipts.map(x => (
                    <div key={x.number} className="px-3 py-2 border-b border-slate-100 last:border-0 flex justify-between items-center text-sm">
                      <div>
                        <div className="font-mono font-medium">{x.number}</div>
                        <div className="text-[11px] text-slate-500 capitalize">{x.type?.replace('_',' ')} · {new Date(x.date).toLocaleDateString('en-IN')}</div>
                      </div>
                      <div className="text-right">
                        <div className="font-mono tabular font-semibold">{inr(x.total)}</div>
                        <div className="text-[10px] uppercase text-slate-500">{x.mode}</div>
                      </div>
                    </div>
                  ))}
                </div>
                {l.receipts_count > 20 && <div className="text-[11px] text-slate-500 mt-2 text-center">Showing latest 20 of {l.receipts_count} receipts</div>}
              </div>
            )}
          </div>
        )}

        <div className="text-center text-[11px] text-slate-500 py-4">
          Balaji Convent & Junior College · Butibori, Nagpur · This is a view-only page. For any query please visit the school office.
        </div>
      </div>
    </div>
  );
}

const Row = ({ label, value, tone, bold }) => (
  <div className="flex justify-between">
    <span className="text-slate-500">{label}</span>
    <span className={`font-mono tabular ${bold ? 'text-lg' : ''} ${tone || 'text-slate-900'}`}>{value}</span>
  </div>
);
