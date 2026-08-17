import React from 'react';
import { V, inrPrint } from '../ReceiptPrimitives';

/**
 * DebitVoucherBody — computer-generated redesign of the legacy paper voucher.
 * Same universal engine (frame + header + footer). Only the middle is unique.
 */
export default function DebitVoucherBody({ r, compact = false }) {
  const meta = r.metadata || {};
  const total = Number(r.total || 0);
  const fs = compact ? 'text-[10px]' : 'text-[11px]';
  const lines = r.lines || [];

  return (
    <div className={`${fs} relative mt-2`}>
      {/* Paid To / Header row */}
      <div className="grid grid-cols-2 gap-3 border" style={{ borderColor: 'var(--line)' }}>
        <Field label="Paid To / Vendor"        value={r.payer_name} big />
        <Field label="Department"              value={r.department_name} />
        <Field label="Voucher No."             value={r.number} mono />
        <Field label="Voucher Date"            value={new Date(r.created_at).toLocaleDateString('en-IN')} mono />
        <Field label="Account Head"            value={meta.account_head || (lines[0]?.fee_head_name)} />
        <Field label="Payment Mode"            value={String(r.payment_mode || '').toUpperCase()} />
        {r.payment_reference && (
          <>
            <Field label="Cheque / DD / Ref."  value={r.payment_reference} mono />
            <Field label="Bank / UPI"          value={meta.bank_name || meta.upi_ref} mono />
          </>
        )}
        <div className="col-span-2 p-2 border-t" style={{ borderColor: 'var(--line)' }}>
          <div className={`uppercase tracking-widest text-slate-500 font-semibold ${compact ? 'text-[8px]' : 'text-[9px]'}`}>Purpose / Particulars</div>
          <div className="mt-0.5">{V(r.purpose || meta.particulars)}</div>
        </div>
      </div>

      {/* Line items */}
      <table className="w-full mt-2 border" style={{ borderColor: 'var(--line)' }}>
        <thead>
          <tr style={{ background: 'var(--brand)', color: 'var(--brand-ink)' }}>
            <th className={`text-center py-1 ${compact ? 'w-8 text-[9px]' : 'w-10 text-[10px]'}`}>SR.</th>
            <th className={`text-left px-2 py-1 ${compact ? 'text-[9px]' : 'text-[10px]'}`}>DESCRIPTION</th>
            <th className={`text-right px-2 py-1 ${compact ? 'text-[9px] w-20' : 'text-[10px] w-24'}`}>AMOUNT (₹)</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((l, i) => (
            <tr key={i} className="border-t" style={{ borderColor: 'var(--line)' }}>
              <td className="text-center py-0.5">{i + 1}</td>
              <td className="px-2 py-0.5">{l.fee_head_name}{l.note ? <span className="text-slate-500 italic"> — {l.note}</span> : null}</td>
              <td className="text-right px-2 py-0.5 font-mono">{inrPrint(l.amount)}</td>
            </tr>
          ))}
          <tr className="border-t-2 font-bold" style={{ background: '#f8fafc', borderColor: 'var(--brand)' }}>
            <td colSpan={2} className="text-right px-2 py-1">TOTAL PAID</td>
            <td className={`text-right px-2 py-1 font-mono ${compact ? 'text-[12px]' : 'text-[13px]'}`}>₹ {inrPrint(total)}</td>
          </tr>
        </tbody>
      </table>

      <div className="grid grid-cols-3 gap-3 mt-2 border" style={{ borderColor: 'var(--line)' }}>
        <div className="col-span-2 p-2 border-r" style={{ borderColor: 'var(--line)' }}>
          <div className={`uppercase tracking-widest text-slate-500 font-semibold ${compact ? 'text-[8px]' : 'text-[9px]'}`}>Amount in Words</div>
          <div className={`font-semibold ${compact ? 'text-[10px]' : 'text-[11px]'}`}>{r.amount_in_words}</div>
        </div>
        <div className="p-2 text-right">
          <div className={`uppercase tracking-widest text-slate-500 font-semibold ${compact ? 'text-[8px]' : 'text-[9px]'}`}>Total Payment</div>
          <div className={`font-black ${compact ? 'text-[16px]' : 'text-[19px]'}`} style={{ color: 'var(--accent)' }}>₹ {inrPrint(total)}</div>
        </div>
      </div>

      <div className={`mt-2 flex justify-between ${compact ? 'text-[9px]' : 'text-[10px]'} text-slate-600`}>
        <span>Created by: <b>{r.cashier_name}</b></span>
        {r.status === 'approved' && r.approved_by_name && <span>Approved by: <b>{r.approved_by_name}</b></span>}
      </div>
    </div>
  );
}

function Field({ label, value, mono = false, big = false }) {
  return (
    <div className={`p-2 border-b ${big ? 'col-span-2' : ''}`} style={{ borderColor: 'var(--line)' }}>
      <div className="uppercase tracking-widest text-slate-500 font-semibold text-[8.5px]">{label}</div>
      <div className={`mt-0.5 ${mono ? 'font-mono' : ''} ${big ? 'font-bold text-[13px]' : ''}`}>{V(value)}</div>
    </div>
  );
}
