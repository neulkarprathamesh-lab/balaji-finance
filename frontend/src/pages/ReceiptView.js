import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import api from '@/lib/api';
import { inr } from '@/components/Layout';
import { Printer, ArrowLeft, XCircle, Copy } from 'lucide-react';
import { toast } from 'sonner';
import { useAuth } from '@/context/AuthContext';
import { QRCodeSVG } from 'qrcode.react';

const LOGO = "https://customer-assets-0z36b82j.emergentagent.net/job_finance-hub-school/artifacts/ce0kfh6k_schoolo%20logo.jpeg";
const rs = (n) => (n == null || n === '' ? '' : Number(n).toFixed(2));

export default function ReceiptView() {
  const { id } = useParams();
  const nav = useNavigate();
  const { user } = useAuth();
  const [r, setR] = useState(null);
  const [twoUp, setTwoUp] = useState(false);
  const load = () => api.get(`/receipts/${id}`).then(res => setR(res.data));
  useEffect(() => { load(); }, [id]);

  const doPrint = async (twoCopies) => {
    setTwoUp(!!twoCopies);
    await api.post(`/receipts/${id}/reprint`);
    setTimeout(() => { window.print(); setTwoUp(false); load(); }, 200);
  };

  const doCancel = async () => {
    const reason = window.prompt('Enter cancellation reason');
    if (!reason) return;
    try { await api.post(`/receipts/${id}/cancel`, { reason }); toast.success('Cancelled'); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); }
  };

  if (!r) return <div className="p-8 text-sm text-slate-500">Loading…</div>;
  const canCancel = ['administrator','manager'].includes(user?.role) && r.status !== 'cancelled';

  const Body = () => (
    r.receipt_type === 'debit_voucher' ? <DebitVoucher r={r} /> :
    r.receipt_type === 'bus' ? <BusReceipt r={r} /> :
    (r.receipt_type === 'general_money' || r.receipt_type === 'general_collection') ? <MoneyReceipt r={r} /> :
    <FeeReceipt r={r} />
  );

  return (
    <div className="min-h-screen bg-slate-100">
      <div className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between no-print">
        <button onClick={() => nav(-1)} className="text-sm text-slate-600 hover:text-slate-900 flex items-center gap-1.5"><ArrowLeft className="w-4 h-4" /> Back</button>
        <div className="flex gap-2">
          {canCancel && <button data-testid="rv-cancel" onClick={doCancel} className="h-9 px-3 border border-red-300 text-red-700 rounded text-sm flex items-center gap-1.5 hover:bg-red-50"><XCircle className="w-4 h-4" /> Cancel Receipt</button>}
          <button data-testid="rv-print-2up" onClick={() => doPrint(true)} className="h-9 px-3 border border-slate-300 rounded text-sm flex items-center gap-1.5 hover:bg-white"><Copy className="w-4 h-4" /> Print Two-Up (Parent + Office)</button>
          <button data-testid="rv-print" onClick={() => doPrint(false)} className="h-9 px-3 bg-blue-600 text-white rounded text-sm flex items-center gap-1.5 hover:bg-blue-700"><Printer className="w-4 h-4" /> Print</button>
        </div>
      </div>

      <div className="max-w-2xl mx-auto p-6">
        <div className="print-page bg-white border border-slate-300 shadow-sm p-6" data-testid="rv-body">
          <Body />
          {twoUp && (
            <>
              <div className="text-center text-[10px] text-slate-500 tracking-widest my-4 border-t-2 border-dashed border-slate-400 pt-1">— — — — — CUT HERE · Parent's Copy above · Office Copy below — — — — —</div>
              <Body />
            </>
          )}
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

/* ============ Fee Receipt (school/admission/misc/dept/refund) — modern A4 design ============ */
function FeeReceipt({ r }) {
  const meta = r.metadata || {};
  const dateStr = new Date(r.created_at).toLocaleDateString('en-IN', { day:'2-digit', month:'short', year:'numeric' });
  const code = r.department_code || '';
  const dept_line1 = { EP: 'BALAJI CONVENT', MP: 'BALAJI CONVENT', SEC: 'BALAJI CONVENT SECONDARY SCHOOL', JC: 'BALAJI CONVENT & JR. COLLEGE' }[code] || 'BALAJI CONVENT & JUNIOR COLLEGE';
  const dept_line2 = { EP: 'ENGLISH PRIMARY SCHOOL', MP: 'MARATHI PRIMARY SCHOOL', SEC: 'SELF FINANCING', JC: 'ARTS, COMMERCE, SCIENCE & BI-FOCAL' }[code] || '';
  const total = Number(r.total || 0);
  const paid = Number(r.total || 0);
  const balance = 0;

  return (
    <div className="text-slate-900 text-[13px]">
      {/* HEADER */}
      <div className="grid grid-cols-12 gap-3 pb-4 border-b-2 border-slate-900">
        <div className="col-span-6 flex items-start gap-3">
          <img src={LOGO} alt="logo" className="w-20 h-20 rounded-full object-cover ring-1 ring-slate-300" />
          <div>
            <div className="font-heading font-black text-xl tracking-tight leading-tight uppercase">{dept_line1}</div>
            <div className="text-[13px] font-bold tracking-wide uppercase text-slate-800">BUTIBORI, NAGPUR</div>
            <div className="text-[10px] text-slate-600 mt-0.5 leading-tight">{dept_line2}</div>
            <div className="text-[10px] text-slate-600">NURSERY TO CLASS 10 (ENGLISH · SEMI ENGLISH · MARATHI)</div>
            <div className="text-[10px] text-slate-600">JUNIOR COLLEGE (SCIENCE · COMMERCE · ARTS) · STATE PATTERN</div>
          </div>
        </div>
        <div className="col-span-3 text-center border-x border-slate-300 px-3">
          <div className="inline-block bg-slate-900 text-white px-4 py-1 font-bold tracking-widest text-[13px]">
            {r.receipt_type === 'refund' ? 'REFUND RECEIPT' : r.receipt_type === 'admission' ? 'ADMISSION RECEIPT' : 'FEE RECEIPT'}
          </div>
          <div className="italic text-slate-600 mt-2 text-[11px] leading-tight">Shaping Tomorrow,<br/>Building Excellence</div>
        </div>
        <div className="col-span-3 text-right text-[11px] space-y-0.5">
          <div className="text-slate-500 uppercase tracking-widest text-[9px]">Receipt No.</div>
          <div className="font-mono font-bold text-slate-900 text-[13px]">{r.number}</div>
          <div className="text-slate-500 uppercase tracking-widest text-[9px] mt-1">Date</div>
          <div className="font-mono font-semibold">{dateStr}</div>
          <div className="text-slate-500 uppercase tracking-widest text-[9px] mt-1">Academic Year</div>
          <div className="font-mono font-semibold">{r.academic_year}</div>
          <div className="flex justify-end mt-1"><QRCodeSVG value={r.number} size={56} level="M" includeMargin={false} /></div>
        </div>
      </div>

      {/* STATUS BANNER */}
      {r.status === 'cancelled' && <div className="text-center text-red-600 font-bold text-sm my-2">*** CANCELLED ***</div>}
      {r.reprint_count > 0 && <div className="text-center text-amber-700 font-semibold text-[11px] my-1">DUPLICATE · Reprint #{r.reprint_count}</div>}

      {/* DETAILS */}
      <div className="mt-3 border border-slate-300">
        <div className="bg-slate-100 border-b border-slate-300 text-center py-1 text-[11px] font-bold tracking-widest">DETAILS</div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 p-3 text-[12px]">
          <Row label="STUDENT NAME" value={r.student_snapshot?.name || r.payer_name} />
          <Row label="FATHER / GUARDIAN" value={meta.guardian_name} />
          <Row label="ADMISSION NO." value={r.student_snapshot?.admission_no} mono />
          <Row label="MOTHER NAME" value={meta.mother_name} />
          <Row label="CLASS / DIVISION" value={meta.class_name} />
          <Row label="CONTACT NO." value={meta.guardian_mobile} mono />
          <Row label="ROLL NO." value={meta.roll_no} />
          <Row label="MEDIUM" value={meta.medium} />
          <Row label="SESSION" value={meta.session || r.academic_year} />
          <Row label="DEPARTMENT" value={r.department_name} />
          {code === 'JC' && <Row label="FACULTI" value={meta.faculti} />}
          <Row label="PATTERN" value={meta.pattern || 'State Pattern'} />
        </div>
      </div>

      {/* FEE TABLE + AMOUNT RECEIVED SIDEBAR */}
      <div className="grid grid-cols-12 gap-3 mt-3">
        <div className="col-span-8">
          <table className="w-full text-[12px] border border-slate-400">
            <thead>
              <tr className="bg-slate-100 border-b border-slate-400 text-[11px]">
                <th className="border-r border-slate-400 py-1.5 px-2 w-12">SR. NO.</th>
                <th className="border-r border-slate-400 py-1.5 px-2 text-left">FEE HEAD</th>
                <th className="border-r border-slate-400 py-1.5 px-2 text-right">TOTAL (₹)</th>
                <th className="border-r border-slate-400 py-1.5 px-2 text-right">PAID (₹)</th>
                <th className="py-1.5 px-2 text-right">BALANCE (₹)</th>
              </tr>
            </thead>
            <tbody>
              {r.lines.map((l, i) => (
                <tr key={i} className="border-b border-slate-300">
                  <td className="border-r border-slate-300 text-center py-1.5">{i + 1}</td>
                  <td className="border-r border-slate-300 px-2 py-1.5 font-medium uppercase">{l.fee_head_name}{l.note ? ` — ${l.note}` : ''}</td>
                  <td className="border-r border-slate-300 px-2 py-1.5 text-right tabular font-mono">{Number(l.amount).toFixed(2)}</td>
                  <td className="border-r border-slate-300 px-2 py-1.5 text-right tabular font-mono">{Number(l.amount).toFixed(2)}</td>
                  <td className="px-2 py-1.5 text-right tabular font-mono">0.00</td>
                </tr>
              ))}
              <tr className="bg-slate-100 border-t-2 border-slate-900 font-bold">
                <td colSpan="2" className="border-r border-slate-400 text-right px-2 py-1.5">TOTAL</td>
                <td className="border-r border-slate-400 px-2 py-1.5 text-right tabular font-mono">{total.toFixed(2)}</td>
                <td className="border-r border-slate-400 px-2 py-1.5 text-right tabular font-mono">{paid.toFixed(2)}</td>
                <td className="px-2 py-1.5 text-right tabular font-mono">{balance.toFixed(2)}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="col-span-4 border border-slate-400">
          <div className="p-3 border-b border-slate-300">
            <div className="text-[9px] uppercase tracking-widest text-slate-500">Amount in Words</div>
            <div className="text-[12px] font-semibold mt-0.5">{r.amount_in_words}</div>
          </div>
          <div className="p-3 border-b border-slate-300">
            <div className="text-[9px] uppercase tracking-widest text-slate-500">Payment Mode</div>
            <div className="text-[13px] font-semibold capitalize">{r.payment_mode}</div>
          </div>
          <div className="p-3 border-b border-slate-300">
            <div className="text-[9px] uppercase tracking-widest text-slate-500">Transaction ID</div>
            <div className="text-[11px] font-mono">{r.payment_reference || `${r.payment_mode.toUpperCase()}/${r.number}`}</div>
          </div>
          <div className="p-3 bg-slate-900 text-white text-center">
            <div className="text-[9px] uppercase tracking-widest text-slate-300">Amount Received</div>
            <div className="font-heading text-2xl font-bold font-mono tabular mt-0.5">₹ {total.toFixed(2)}</div>
          </div>
        </div>
      </div>

      {/* NOTES + SIGNATURES */}
      <div className="grid grid-cols-3 gap-6 mt-4 text-[11px]">
        <div>
          <div className="font-bold text-[10px] tracking-widest text-slate-600 mb-1">NOTES:</div>
          <ul className="text-slate-600 space-y-0.5 list-disc pl-4">
            <li>This is a computer generated receipt.</li>
            <li>No signature is required.</li>
            <li>Fees once paid will not be refunded.</li>
            <li>Please preserve this receipt for your records.</li>
          </ul>
        </div>
        <div className="text-center pt-6">
          <div className="border-t border-slate-500 pt-1 text-[10px] tracking-widest">RECEIVED BY</div>
          <div className="text-[10px] text-slate-600">{r.cashier_name}</div>
        </div>
        <div className="text-center pt-6">
          <div className="border-t border-slate-500 pt-1 text-[10px] tracking-widest">AUTHORIZED BY</div>
        </div>
      </div>

      {/* FOOTER */}
      <div className="mt-4 pt-2 border-t border-slate-300 flex justify-between items-center text-[10px] text-slate-600">
        <span>📍 Butibori, Nagpur — 441122, Maharashtra</span>
        <span>📞 07103-234567</span>
        <span>✉ info@balajiconventbutibori.edu.in</span>
      </div>
    </div>
  );
}

const Row = ({ label, value, mono }) => (
  <div className="flex gap-2">
    <span className="text-slate-500 min-w-[130px]">{label}</span>
    <span className="text-slate-400">:</span>
    <span className={`font-semibold flex-1 ${mono ? 'font-mono' : ''}`}>{value || '—'}</span>
  </div>
);

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
