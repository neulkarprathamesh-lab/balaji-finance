import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '@/lib/api';
import { inr } from '@/components/Layout';
import { Printer, ArrowLeft, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/context/AuthContext';

export default function ReceiptView() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [r, setR] = useState(null);
  const load = () => api.get(`/receipts/${id}`).then(res => setR(res.data));
  useEffect(() => { load(); }, [id]);

  const doPrint = async () => {
    await api.post(`/receipts/${id}/reprint`);
    window.print();
    load();
  };

  const doCancel = async () => {
    const reason = window.prompt('Enter cancellation reason');
    if (!reason) return;
    try { await api.post(`/receipts/${id}/cancel`, { reason }); toast.success('Cancelled'); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); }
  };

  if (!r) return <div className="p-8 text-sm text-slate-500">Loading…</div>;
  const canCancel = ['administrator','manager'].includes(user?.role) && r.status !== 'cancelled';

  return (
    <div className="min-h-screen bg-slate-100">
      <div className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between no-print">
        <button onClick={() => nav(-1)} className="text-sm text-slate-600 hover:text-slate-900 flex items-center gap-1.5"><ArrowLeft className="w-4 h-4" /> Back</button>
        <div className="flex gap-2">
          {canCancel && <button data-testid="rv-cancel" onClick={doCancel} className="h-9 px-3 border border-red-300 text-red-700 rounded text-sm flex items-center gap-1.5 hover:bg-red-50"><XCircle className="w-4 h-4" /> Cancel Receipt</button>}
          <button data-testid="rv-print" onClick={doPrint} className="h-9 px-3 bg-blue-600 text-white rounded text-sm flex items-center gap-1.5 hover:bg-blue-700"><Printer className="w-4 h-4" /> Print</button>
        </div>
      </div>

      <div className="max-w-3xl mx-auto p-6">
        <div className="print-page bg-white border border-slate-300 p-8 shadow-sm">
          <div className="text-center border-b-2 border-slate-900 pb-3 mb-4">
            <div className="font-heading text-2xl font-bold tracking-tight">BALAJI CONVENT & JUNIOR COLLEGE</div>
            <div className="text-[12px] text-slate-700">Butibori, Nagpur · {r.department_name}</div>
            <div className="text-[11px] tracking-widest uppercase mt-1 text-slate-600">
              {r.receipt_type === 'debit_voucher' ? 'Debit Voucher' : 'Money Receipt'}
              {r.status === 'cancelled' && <span className="ml-2 text-red-600">· CANCELLED</span>}
              {r.reprint_count > 0 && <span className="ml-2 text-amber-700">· DUPLICATE (Reprint #{r.reprint_count})</span>}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 text-sm mb-4">
            <div><span className="text-slate-500">Receipt No: </span><span className="font-mono font-semibold">{r.number}</span></div>
            <div className="text-right"><span className="text-slate-500">Date: </span>{new Date(r.created_at).toLocaleString('en-IN')}</div>
            {r.student_snapshot && <>
              <div><span className="text-slate-500">Admission No: </span><span className="font-mono">{r.student_snapshot.admission_no}</span></div>
              <div className="text-right"><span className="text-slate-500">Academic Year: </span>{r.academic_year}</div>
              <div className="col-span-2"><span className="text-slate-500">Student: </span><span className="font-semibold">{r.student_snapshot.name}</span></div>
            </>}
            {!r.student_snapshot && r.payer_name && <div className="col-span-2"><span className="text-slate-500">Received from: </span><span className="font-semibold">{r.payer_name}</span></div>}
            {r.purpose && <div className="col-span-2"><span className="text-slate-500">Purpose: </span>{r.purpose}</div>}
          </div>

          <table className="w-full text-sm border-t border-b border-slate-400 my-3">
            <thead>
              <tr className="border-b border-slate-400"><th className="text-left py-1.5">#</th><th className="text-left">Particulars</th><th className="text-right">Amount</th></tr>
            </thead>
            <tbody>
              {r.lines.map((l, i) => (
                <tr key={i} className="border-b border-slate-200">
                  <td className="py-1.5">{i+1}</td>
                  <td>{l.fee_head_name}{l.note ? ` — ${l.note}` : ''}</td>
                  <td className="text-right tabular">{inr(l.amount)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr><td colSpan="2" className="text-right font-semibold py-2">TOTAL</td><td className="text-right font-mono font-bold tabular text-base">{inr(r.total)}</td></tr>
            </tfoot>
          </table>

          <div className="text-sm mb-3"><span className="text-slate-500">In words: </span><span className="italic">{r.amount_in_words}</span></div>
          <div className="grid grid-cols-2 gap-3 text-sm mb-8">
            <div><span className="text-slate-500">Payment mode: </span><span className="uppercase">{r.payment_mode}</span>{r.payment_reference ? ` · Ref: ${r.payment_reference}` : ''}</div>
            <div className="text-right"><span className="text-slate-500">Cashier: </span>{r.cashier_name}</div>
          </div>
          {r.remarks && <div className="text-[12px] text-slate-600 mb-6">Remarks: {r.remarks}</div>}

          <div className="grid grid-cols-2 gap-8 mt-12 text-[11px] text-slate-600">
            <div className="border-t border-slate-400 pt-1 text-center">Payer's Signature</div>
            <div className="border-t border-slate-400 pt-1 text-center">Authorised Signatory</div>
          </div>
          <div className="text-center text-[10px] text-slate-500 mt-4 border-t border-slate-200 pt-2">This is a computer-generated receipt.</div>
        </div>
      </div>
    </div>
  );
}
