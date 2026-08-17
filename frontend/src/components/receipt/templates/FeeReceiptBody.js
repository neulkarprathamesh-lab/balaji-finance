import React from 'react';
import { V, inrPrint } from '../ReceiptPrimitives';

const Row = ({ label, value, mono = false }) => (
  <div className="flex items-start py-[1.5px]">
    <div className="uppercase tracking-wide text-slate-600 font-semibold" style={{ width: '38%', fontSize: 'inherit' }}>{label}</div>
    <div className="text-slate-500">:</div>
    <div className={`pl-1.5 flex-1 ${mono ? 'font-mono' : ''}`}>{V(value)}</div>
  </div>
);

/**
 * FeeReceiptBody — the "middle" of a school/admission/misc/refund receipt.
 * The universal engine surrounds this with header + footer, so we render only
 * the details table + line items + totals here.
 */
export default function FeeReceiptBody({ r, compact = false }) {
  const meta = r.metadata || {};
  const snapshot = r.student_snapshot || {};
  const lines = r.lines || [];
  const total = Number(r.total || 0);
  const fs = compact ? 'text-[10px]' : 'text-[11px]';

  return (
    <div className={`${fs} relative mt-2`}>
      {/* DETAILS */}
      <div className="border" style={{ borderColor: 'var(--line)' }}>
        <div className={`text-center py-0.5 font-bold tracking-widest ${compact ? 'text-[9px]' : 'text-[10px]'}`} style={{ background: 'var(--brand)', color: 'var(--brand-ink)' }}>DETAILS</div>
        <div className="grid grid-cols-2 gap-x-4 px-2 py-1.5">
          <div>
            <Row label="Student Name"    value={snapshot.name || r.payer_name} />
            <Row label="Admission No."   value={snapshot.admission_no} mono />
            <Row label="Class / Division" value={`${meta.class_name || snapshot.class_name || '—'}${snapshot.section ? ' / ' + snapshot.section : ''}`} />
            <Row label="Roll No."        value={meta.roll_no || snapshot.roll_no} mono />
          </div>
          <div>
            <Row label="Father Name"     value={meta.father_name || snapshot.father_name} />
            <Row label="Mother Name"     value={meta.mother_name || snapshot.mother_name} />
            <Row label="Contact No."     value={meta.guardian_mobile || snapshot.guardian_mobile} mono />
            <Row label="Medium"          value={snapshot.medium} />
            {snapshot.stream && <Row label="Stream" value={snapshot.stream} />}
            {snapshot.bus_stop_name && <Row label="Bus Stop" value={`#${snapshot.bus_stop_no} · ${snapshot.bus_stop_name}`} />}
          </div>
        </div>
      </div>

      {/* LINE ITEMS TABLE */}
      <table className="w-full mt-2 border" style={{ borderColor: 'var(--line)' }}>
        <thead>
          <tr style={{ background: 'var(--brand)', color: 'var(--brand-ink)' }}>
            <th className={`text-center py-1 ${compact ? 'w-8 text-[9px]' : 'w-10 text-[10px]'}`}>SR.</th>
            <th className={`text-left px-2 py-1 ${compact ? 'text-[9px]' : 'text-[10px]'}`}>FEE HEAD / DESCRIPTION</th>
            <th className={`text-right px-2 py-1 ${compact ? 'text-[9px] w-20' : 'text-[10px] w-24'}`}>AMOUNT (₹)</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((l, i) => (
            <tr key={i} className="border-t" style={{ borderColor: 'var(--line)' }}>
              <td className="text-center py-0.5">{i + 1}</td>
              <td className="px-2 py-0.5">
                <div className="uppercase font-medium">{l.fee_head_name}</div>
                {l.note && <div className={`italic ${compact ? 'text-[8.5px]' : 'text-[9px]'} text-slate-500`}>{l.note}</div>}
              </td>
              <td className="text-right px-2 py-0.5 font-mono">{inrPrint(l.amount)}</td>
            </tr>
          ))}
          <tr className="border-t-2 font-bold" style={{ background: '#f8fafc', borderColor: 'var(--brand)' }}>
            <td colSpan={2} className="text-right px-2 py-1">TOTAL</td>
            <td className={`text-right px-2 py-1 font-mono ${compact ? 'text-[12px]' : 'text-[13px]'}`}>{inrPrint(total)}</td>
          </tr>
        </tbody>
      </table>

      {/* FOOTER META */}
      <div className="grid grid-cols-3 gap-3 mt-2 border" style={{ borderColor: 'var(--line)' }}>
        <div className="p-2 border-r" style={{ borderColor: 'var(--line)' }}>
          <div className={`uppercase tracking-widest text-slate-500 font-semibold ${compact ? 'text-[8px]' : 'text-[9px]'}`}>Amount in Words</div>
          <div className={`font-semibold ${compact ? 'text-[10px]' : 'text-[11px]'}`}>{r.amount_in_words}</div>
        </div>
        <div className="p-2 border-r" style={{ borderColor: 'var(--line)' }}>
          <div className={`uppercase tracking-widest text-slate-500 font-semibold ${compact ? 'text-[8px]' : 'text-[9px]'}`}>Payment Mode</div>
          <div className={`font-semibold uppercase ${compact ? 'text-[10px]' : 'text-[11px]'}`}>{r.payment_mode}</div>
          {r.payment_reference && (
            <div className={`text-slate-500 font-mono ${compact ? 'text-[8.5px]' : 'text-[9px]'}`}>{r.payment_reference}</div>
          )}
        </div>
        <div className="p-2 text-right">
          <div className={`uppercase tracking-widest text-slate-500 font-semibold ${compact ? 'text-[8px]' : 'text-[9px]'}`}>Amount Received</div>
          <div className={`font-black ${compact ? 'text-[16px]' : 'text-[19px]'}`} style={{ color: 'var(--accent)' }}>₹ {inrPrint(total)}</div>
        </div>
      </div>
    </div>
  );
}
