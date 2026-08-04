import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '@/lib/api';
import { PageHeader, inr } from '@/components/Layout';

export default function Receipts() {
  const [rows, setRows] = useState([]);
  const [type, setType] = useState('');
  const [q, setQ] = useState('');
  const [df, setDf] = useState('');
  const [dt, setDt] = useState('');
  const nav = useNavigate();

  const load = () => {
    const p = new URLSearchParams();
    if (type) p.set('receipt_type', type);
    if (q) p.set('q', q);
    if (df) p.set('date_from', df);
    if (dt) p.set('date_to', dt);
    api.get(`/receipts?${p.toString()}`).then(r => setRows(r.data));
  };
  useEffect(load, []);

  return (
    <>
      <PageHeader title="Receipts" subtitle={`${rows.length} results`} />
      <div className="p-6 space-y-4">
        <div className="bg-white border border-slate-200 rounded p-4 flex gap-3 items-end flex-wrap">
          <div>
            <div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">Receipt No</div>
            <input value={q} onChange={e=>setQ(e.target.value)} className="h-9 px-3 border border-slate-300 rounded text-sm w-40" placeholder="EP-2026-…" />
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">Type</div>
            <select value={type} onChange={e=>setType(e.target.value)} className="h-9 px-3 border border-slate-300 rounded text-sm bg-white">
              <option value="">All types</option>
              {['school','admission','bus','misc','department','general_money','refund','debit_voucher','general_collection'].map(t => <option key={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">From</div>
            <input type="date" value={df} onChange={e=>setDf(e.target.value)} className="h-9 px-3 border border-slate-300 rounded text-sm" />
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">To</div>
            <input type="date" value={dt} onChange={e=>setDt(e.target.value)} className="h-9 px-3 border border-slate-300 rounded text-sm" />
          </div>
          <button onClick={load} className="h-9 px-4 bg-slate-900 text-white text-sm rounded">Filter</button>
        </div>

        <div className="bg-white border border-slate-200 rounded overflow-hidden">
          <table className="w-full dense-table">
            <thead><tr className="text-left text-[11px] uppercase tracking-wide text-slate-600"><th>Number</th><th>Type</th><th>Payer</th><th>Dept</th><th>Mode</th><th className="text-right">Amount</th><th>Cashier</th><th>Status</th><th>Date</th></tr></thead>
            <tbody>
              {rows.length === 0 && <tr><td colSpan="9" className="text-center py-8 text-slate-500">No receipts found</td></tr>}
              {rows.map(r => (
                <tr key={r.id} className="cursor-pointer" onClick={() => nav(`/receipts/${r.id}`)}>
                  <td className="font-mono text-[12px]">{r.number}</td>
                  <td className="capitalize text-slate-600 text-[12px]">{r.receipt_type?.replace('_',' ')}</td>
                  <td className="font-medium">{r.payer_name || '-'}</td>
                  <td>{r.department_code}</td>
                  <td className="uppercase text-[11px]">{r.payment_mode}</td>
                  <td className="text-right tabular font-medium">{inr(r.total)}</td>
                  <td className="text-[12px] text-slate-600">{r.cashier_name}</td>
                  <td><span className={`text-[11px] px-1.5 py-0.5 rounded ${r.status==='cancelled'?'bg-red-100 text-red-800':'bg-emerald-100 text-emerald-800'}`}>{r.status}</span></td>
                  <td className="text-[12px] text-slate-500">{new Date(r.created_at).toLocaleString('en-IN')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
