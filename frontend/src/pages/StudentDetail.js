import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '@/lib/api';
import { PageHeader, inr } from '@/components/Layout';
import { Receipt as ReceiptIcon, FileEdit, CalendarClock } from 'lucide-react';

export default function StudentDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [data, setData] = useState(null);
  useEffect(() => { api.get(`/students/${id}/ledger`).then(r => setData(r.data)); }, [id]);
  if (!data) return <div className="p-8 text-sm text-slate-500">Loading…</div>;
  const s = data.student;

  return (
    <>
      <PageHeader title={s.name} subtitle={`Admission No: ${s.admission_no}`}
        actions={
          <div className="flex gap-2">
            <button data-testid="sd-new-receipt" onClick={() => nav(`/new-receipt?student=${id}`)} className="h-9 px-3 bg-blue-600 text-white rounded text-sm flex items-center gap-1.5 hover:bg-blue-700"><ReceiptIcon className="w-4 h-4" /> New Receipt</button>
            <button onClick={() => nav(`/adjustments?student=${id}`)} className="h-9 px-3 border border-slate-300 rounded text-sm flex items-center gap-1.5 hover:bg-slate-100"><FileEdit className="w-4 h-4" /> Adjustment</button>
            <button onClick={() => nav(`/extensions?student=${id}`)} className="h-9 px-3 border border-slate-300 rounded text-sm flex items-center gap-1.5 hover:bg-slate-100"><CalendarClock className="w-4 h-4" /> Extension</button>
          </div>
        }
      />
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-4 gap-4">
          <Card label="Total Fees" value={inr(data.fee_structure?.total || 0)} />
          <Card label="Paid" value={inr(data.total_paid)} tone="text-emerald-700" />
          <Card label="Adjustments" value={inr(data.total_adjusted)} />
          <Card label="Outstanding" value={inr(data.outstanding)} tone="text-red-700" />
        </div>

        <div className="bg-white border border-slate-200 rounded">
          <div className="px-4 py-3 border-b border-slate-200"><h3 className="font-heading font-medium">Receipts</h3></div>
          <table className="w-full dense-table">
            <thead><tr className="text-left text-[11px] uppercase tracking-wide text-slate-600"><th>Number</th><th>Type</th><th>Mode</th><th className="text-right">Amount</th><th>Status</th><th>Date</th></tr></thead>
            <tbody>
              {data.receipts.length === 0 && <tr><td colSpan="6" className="text-center py-6 text-slate-500">No receipts yet</td></tr>}
              {data.receipts.map(r => (
                <tr key={r.id} className="cursor-pointer" onClick={() => nav(`/receipts/${r.id}`)}>
                  <td className="font-mono text-[12px]">{r.number}</td>
                  <td className="capitalize text-slate-600">{r.receipt_type?.replace('_',' ')}</td>
                  <td className="uppercase text-[11px]">{r.payment_mode}</td>
                  <td className="text-right tabular font-medium">{inr(r.total)}</td>
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
const Card = ({ label, value, tone='text-slate-900' }) => (
  <div className="bg-white border border-slate-200 rounded p-4">
    <div className="text-[11px] tracking-widest uppercase text-slate-500">{label}</div>
    <div className={`font-heading text-2xl font-semibold tabular mt-1 ${tone}`}>{value}</div>
  </div>
);
