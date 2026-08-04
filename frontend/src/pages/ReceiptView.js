import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '@/lib/api';
import { inr } from '@/components/Layout';
import { Printer, ArrowLeft, XCircle } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/context/AuthContext';

const LOGO = "https://customer-assets-0z36b82j.emergentagent.net/job_finance-hub-school/artifacts/ce0kfh6k_schoolo%20logo.jpeg";
const rs = (n) => (n == null || n === '' ? '' : Number(n).toFixed(2));

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

      <div className="max-w-2xl mx-auto p-6">
        <div className="print-page bg-white border border-slate-300 shadow-sm p-6" data-testid="rv-body">
          {r.receipt_type === 'debit_voucher' ? <DebitVoucher r={r} /> :
           r.receipt_type === 'bus' ? <BusReceipt r={r} /> :
           (r.receipt_type === 'general_money' || r.receipt_type === 'general_collection') ? <MoneyReceipt r={r} /> :
           <FeeReceipt r={r} />}
        </div>
      </div>
    </div>
  );
}

/* ============ Common Header ============ */
function Header({ r, boxLabel = 'RECEIPT' }) {
  const meta = r.metadata || {};
  const code = r.department_code || '';
  const defaults = {
    EP: ['BALAJI CONVENT', 'ENGLISH PRIMARY SCHOOL'],
    MP: ['BALAJI CONVENT', 'MARATHI PRIMARY SCHOOL'],
    SEC: ['BALAJI CONVENT SECONDARY SCHOOL', 'SELF FINANCING'],
    JC: ['BALAJI CONVENT JR. COLLEGE', 'ARTS, COMMERCE, SCIENCE & BI-FOCAL'],
  };
  const fallback = defaults[code] || ['BALAJI CONVENT', (r.department_name || '').toUpperCase()];
  const line1 = meta.header_line1 || r.department_header1 || fallback[0];
  const line2 = meta.header_line2 || r.department_header2 || fallback[1];
  return (
    <div className="text-center">
      <div className="flex items-center justify-center gap-3">
        <img src={LOGO} alt="logo" className="w-14 h-14 rounded-full object-cover" />
        <div>
          <div className="font-heading font-black text-xl tracking-tight leading-tight">{line1}</div>
          {line2 && <div className="text-[13px] font-semibold tracking-wide">{line2}</div>}
          <div className="text-[11px] text-slate-700">BUTI-BORI, DIST. NAGPUR</div>
        </div>
      </div>
      <div className="inline-block border-2 border-slate-900 px-4 py-0.5 mt-2 font-bold tracking-widest text-[13px]">{boxLabel}</div>
      {r.status === 'cancelled' && <div className="text-red-600 font-bold text-sm mt-1">*** CANCELLED ***</div>}
      {r.reprint_count > 0 && <div className="text-amber-700 font-semibold text-[11px] mt-1">DUPLICATE · Reprint #{r.reprint_count}</div>}
    </div>
  );
}

function Footer({ r }) {
  return (
    <>
      {r.remarks && <div className="text-[11px] text-slate-600 mt-2">Remarks: {r.remarks}</div>}
      <div className="text-[10px] text-slate-500 text-center mt-4 border-t border-slate-200 pt-1">This is a computer-generated receipt · Issued by {r.cashier_name}</div>
    </>
  );
}

/* ============ Fee Receipt (school/admission/misc/dept/refund) ============ */
function FeeReceipt({ r }) {
  const meta = r.metadata || {};
  const dateStr = new Date(r.created_at).toLocaleDateString('en-IN');
  // Ensure at least 5 rows (matching the physical book)
  const rows = [...r.lines];
  while (rows.length < 5) rows.push({ fee_head_name: '', amount: '' });

  return (
    <>
      <Header r={r} boxLabel={r.receipt_type === 'refund' ? 'REFUND RECEIPT' : 'RECEIPT'} />

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-4 text-[13px]">
        <div>No. <span className="font-mono font-bold text-red-700 text-base">{r.number}</span></div>
        <div className="text-right">Date: <span className="border-b border-slate-500 inline-block min-w-[100px] font-mono">{dateStr}</span></div>
      </div>

      <div className="mt-3 space-y-1.5 text-[13px]">
        <div className="flex gap-2"><span>Name</span><span className="border-b border-slate-500 flex-1 pl-1 font-medium">{r.student_snapshot?.name || r.payer_name || ''}</span></div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex gap-2"><span>Class</span><span className="border-b border-slate-500 flex-1 pl-1">{meta.class_name || ''}</span></div>
          <div className="flex gap-2"><span>{r.department_code === 'JC' ? 'Faculti' : 'Adm. No.'}</span><span className="border-b border-slate-500 flex-1 pl-1">{meta.faculti || r.student_snapshot?.admission_no || ''}</span></div>
        </div>
        <div className="flex gap-2"><span>Session</span><span className="border-b border-slate-500 flex-1 pl-1 font-mono">{meta.session || r.academic_year || ''}</span></div>
      </div>

      <table className="w-full text-[13px] border border-slate-900 mt-3">
        <thead>
          <tr className="border-b border-slate-900">
            <th className="border-r border-slate-900 py-1 px-1 w-12 text-center">Sr.<br/>No.</th>
            <th className="border-r border-slate-900 py-1 px-2 text-left">PARTICULARS</th>
            <th className="border-r border-slate-900 py-1 px-2 text-center w-20">Rs.</th>
            <th className="py-1 px-2 text-center w-14">Ps.</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((l, i) => {
            const amt = l.amount ? Number(l.amount) : null;
            const rupees = amt != null ? Math.floor(amt) : '';
            const paise = amt != null ? String(Math.round((amt - Math.floor(amt)) * 100)).padStart(2, '0') : '';
            return (
              <tr key={i} className="border-b border-slate-400">
                <td className="border-r border-slate-900 text-center py-1.5">{i + 1})</td>
                <td className="border-r border-slate-900 px-2 py-1.5 font-medium">{l.fee_head_name || ''}{l.note ? ` — ${l.note}` : ''}</td>
                <td className="border-r border-slate-900 px-2 py-1.5 text-right tabular font-mono">{rupees !== '' ? rupees : ''}</td>
                <td className="px-2 py-1.5 text-right tabular font-mono">{paise}</td>
              </tr>
            );
          })}
          <tr className="border-t-2 border-slate-900 bg-slate-50">
            <td colSpan="2" className="border-r border-slate-900 text-right px-2 py-1.5 font-bold">TOTAL</td>
            <td className="border-r border-slate-900 px-2 py-1.5 text-right tabular font-mono font-bold">{Math.floor(r.total)}</td>
            <td className="px-2 py-1.5 text-right tabular font-mono font-bold">{String(Math.round((r.total - Math.floor(r.total)) * 100)).padStart(2,'0')}</td>
          </tr>
        </tbody>
      </table>

      <div className="mt-3 text-[13px]">
        <div className="flex gap-2"><span>Rs. (in words)</span><span className="border-b border-slate-500 flex-1 pl-1 italic">{r.amount_in_words}</span></div>
      </div>

      <div className="flex justify-between items-end mt-8 text-[13px]">
        <div>Payment: <span className="font-semibold">{r.payment_mode === 'cash' ? 'Cash' : r.payment_mode === 'online' ? 'Online' : `${r.payment_mode.toUpperCase()}${r.payment_reference ? ` — ${r.payment_reference}` : ''}`}</span></div>
        <div className="text-center"><div className="border-t border-slate-500 pt-0.5 px-6">Received By</div><div className="text-[11px] text-slate-600">{r.cashier_name}</div></div>
      </div>

      <Footer r={r} />
    </>
  );
}

/* ============ Bus Fee Receipt ============ */
function BusReceipt({ r }) {
  const meta = r.metadata || {};
  const dateStr = new Date(r.created_at).toLocaleDateString('en-IN');
  return (
    <div className="border-4 border-double border-amber-800 p-4 bg-amber-50/40">
      <Header r={r} boxLabel="BUS FEE RECEIPT" />

      <div className="grid grid-cols-2 gap-x-4 gap-y-1 mt-4 text-[13px]">
        <div>R.No. <span className="font-mono font-bold text-red-700 text-base">{r.number}</span></div>
        <div className="text-right">Date <span className="border-b border-slate-500 inline-block min-w-[100px] font-mono">{dateStr}</span></div>
      </div>

      <div className="mt-3 space-y-1.5 text-[13px]">
        <div className="flex gap-2"><span>Name</span><span className="border-b border-slate-500 flex-1 pl-1 font-medium">{r.student_snapshot?.name || r.payer_name || ''}</span></div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex gap-2"><span>Class</span><span className="border-b border-slate-500 flex-1 pl-1">{meta.class_name || ''}</span></div>
          <div className="flex gap-2"><span>Bus No.</span><span className="border-b border-slate-500 flex-1 pl-1 font-mono">{meta.bus_no || ''}</span></div>
        </div>
        <div className="flex gap-2"><span>Village Name</span><span className="border-b border-slate-500 flex-1 pl-1">{meta.village_name || ''}</span></div>
        <div className="grid grid-cols-2 gap-3">
          <div className="flex gap-2"><span>For the Month of</span><span className="border-b border-slate-500 flex-1 pl-1">{meta.month || ''}</span></div>
          <div className="flex gap-2"><span>Session</span><span className="border-b border-slate-500 flex-1 pl-1 font-mono">{meta.session || r.academic_year || ''}</span></div>
        </div>
        <div className="flex gap-2"><span>Rs. in words</span><span className="border-b border-slate-500 flex-1 pl-1 italic">{r.amount_in_words}</span></div>
      </div>

      <div className="flex items-center justify-between mt-4">
        <div className="border-2 border-slate-900 px-6 py-2 text-lg font-bold font-mono tabular">₹ {rs(r.total)}</div>
        <div className="text-right text-[13px]">
          <div>Payment Mode: <span className="font-semibold">{r.payment_mode === 'cash' ? 'Cash' : 'Online'}</span></div>
        </div>
      </div>

      <div className="mt-10 text-right text-[12px]">
        <div className="inline-block border-t border-slate-500 pt-0.5 px-6">Sign of Receiver</div>
        <div className="text-[11px] text-slate-600">{r.cashier_name}</div>
      </div>
      <Footer r={r} />
    </div>
  );
}

/* ============ General Money Receipt ("Received with thanks from") ============ */
function MoneyReceipt({ r }) {
  const meta = r.metadata || {};
  const dateStr = new Date(r.created_at).toLocaleDateString('en-IN');
  const [yrFrom, yrTo] = (meta.session || r.academic_year || '20-20').split('-');
  return (
    <div className="border-4 border-double border-teal-700 p-4 bg-teal-50/30">
      <Header r={r} boxLabel="RECEIPT" />

      <div className="mt-4 text-[13px]">
        <div className="grid grid-cols-2 gap-4">
          <div>No. <span className="font-mono font-bold text-red-700 text-base">{r.number}</span></div>
          <div className="text-right">Date <span className="border-b border-slate-500 inline-block min-w-[100px] font-mono">{dateStr}</span></div>
        </div>
      </div>

      <div className="mt-4 space-y-2.5 text-[13px] leading-relaxed">
        <div>Received with thanks from <span className="border-b border-slate-500 inline-block min-w-[280px] pl-1 font-medium">{r.payer_name || r.student_snapshot?.name || ''}</span></div>
        <div className="grid grid-cols-2 gap-3">
          <div>Class <span className="border-b border-slate-500 inline-block min-w-[80px] pl-1">{meta.class_name || ''}</span></div>
          <div>Session — 20<span className="border-b border-slate-500 inline-block w-8 pl-1 font-mono">{(yrFrom || '').slice(-2)}</span> — 20<span className="border-b border-slate-500 inline-block w-8 pl-1 font-mono">{(yrTo || '').slice(-2)}</span></div>
        </div>
        <div>the sum of Rupees <span className="border-b border-slate-500 inline-block min-w-[320px] pl-1 italic">{r.amount_in_words}</span></div>
        <div>by Cash / D.D. No. <span className="border-b border-slate-500 inline-block min-w-[220px] pl-1 font-mono">{r.payment_reference || (r.payment_mode === 'cash' ? '— Cash —' : '')}</span></div>
        <div>On account of <span className="border-b border-slate-500 inline-block min-w-[320px] pl-1">{r.purpose || meta.on_account_of || ''}</span></div>
      </div>

      <div className="flex items-center justify-between mt-6">
        <div className="border-2 border-slate-900 px-4 py-2 text-lg font-bold font-mono tabular">₹ {rs(r.total)}</div>
        <div className="text-right">
          <div className="inline-block border-t border-slate-500 pt-0.5 px-6 text-[12px] italic">Signature of Representative</div>
          <div className="text-[11px] text-slate-600">{r.cashier_name}</div>
        </div>
      </div>
      <Footer r={r} />
    </div>
  );
}

/* ============ Debit Voucher ============ */
function DebitVoucher({ r }) {
  const meta = r.metadata || {};
  const dateStr = new Date(r.created_at).toLocaleDateString('en-IN');
  const rows = [...r.lines];
  while (rows.length < 4) rows.push({ fee_head_name: '', amount: '' });

  return (
    <div className="border-2 border-slate-900 p-4">
      <div className="text-center">
        <div className="font-heading font-black text-xl tracking-tight">BALAJI CONVENT SCHOOL</div>
        <div className="text-[11px] text-slate-700">At Post Buti-Bori, Tah, Dist-Nagpur-441108</div>
        <div className="inline-block bg-slate-900 text-white px-3 py-0.5 mt-2 font-bold tracking-widest text-[12px]">DEBIT VOUCHER</div>
        {r.status === 'cancelled' && <div className="text-red-600 font-bold text-sm mt-1">*** CANCELLED ***</div>}
      </div>

      <div className="grid grid-cols-2 gap-4 mt-4 text-[13px]">
        <div>Voucher No. <span className="font-mono font-bold text-red-700">{r.number}</span></div>
        <div className="text-right">Date : <span className="border-b border-slate-500 inline-block min-w-[100px] font-mono">{dateStr}</span></div>
      </div>

      <div className="mt-3 space-y-2 text-[13px]">
        <div className="flex gap-2"><span>Paid to :</span><span className="border-b border-slate-500 flex-1 pl-1 font-medium">{meta.paid_to || r.payer_name || ''}</span></div>
        <div className="flex gap-2"><span>A/C H :</span><span className="border-b border-slate-500 flex-1 pl-1">{meta.ac_head || r.purpose || ''}</span></div>
      </div>

      <table className="w-full text-[13px] border border-slate-900 mt-3">
        <thead>
          <tr className="border-b border-slate-900">
            <th className="border-r border-slate-900 py-1 px-2 text-left">Particular</th>
            <th className="border-r border-slate-900 py-1 px-2 text-center w-24">Rs.</th>
            <th className="py-1 px-2 text-center w-14">Ps.</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((l, i) => {
            const amt = l.amount ? Number(l.amount) : null;
            return (
              <tr key={i} className="border-b border-slate-400">
                <td className="border-r border-slate-900 px-2 py-1.5">{l.fee_head_name || ''}{l.note ? ` — ${l.note}` : ''}</td>
                <td className="border-r border-slate-900 px-2 py-1.5 text-right font-mono">{amt != null ? Math.floor(amt) : ''}</td>
                <td className="px-2 py-1.5 text-right font-mono">{amt != null ? String(Math.round((amt - Math.floor(amt)) * 100)).padStart(2,'0') : ''}</td>
              </tr>
            );
          })}
          <tr className="border-t-2 border-slate-900 bg-slate-50">
            <td className="border-r border-slate-900 text-right px-2 py-1.5 font-bold">Net Total</td>
            <td className="border-r border-slate-900 px-2 py-1.5 text-right font-mono font-bold">{Math.floor(r.total)}</td>
            <td className="px-2 py-1.5 text-right font-mono font-bold">{String(Math.round((r.total - Math.floor(r.total)) * 100)).padStart(2,'0')}</td>
          </tr>
        </tbody>
      </table>

      <div className="mt-3 text-[13px]">
        <div className="flex gap-2"><span>Amount (in Words) Rs.</span><span className="border-b border-slate-500 flex-1 pl-1 italic">{r.amount_in_words}</span></div>
      </div>

      <div className="grid grid-cols-2 gap-8 mt-14 text-[11px]">
        <div>
          <div className="border-t border-slate-500 pt-0.5 text-center">Principal</div>
          <div className="border-t border-slate-500 pt-0.5 mt-10 text-center">Director</div>
        </div>
        <div>
          <div className="border-t border-slate-500 pt-0.5 text-center">Payees Sign</div>
          <div className="border-t border-slate-500 pt-0.5 mt-10 text-center">Receiver Sign</div>
        </div>
      </div>
      <Footer r={r} />
    </div>
  );
}
