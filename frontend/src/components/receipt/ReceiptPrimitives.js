import React from 'react';
import { QRCodeSVG } from 'qrcode.react';

export const LOGO = '/school-logo.jpeg';

/** Small utility to safely render a value or an em-dash. */
export const V = (v) => (v == null || v === '' ? <span className="text-slate-400">—</span> : v);

/** INR formatter used across every printable. */
export const inrPrint = (n) => new Intl.NumberFormat('en-IN', { minimumFractionDigits: 2 }).format(Number(n || 0));

/**
 * Header — one component for every receipt / voucher / notice.
 * Adjusts to A5 automatically: smaller logo, tighter typography.
 * `boxLabel` = "FEE RECEIPT" | "DEBIT VOUCHER" | "BUS RECEIPT" | …
 * `tagline` = "Shaping Tomorrow, Building Excellence" or custom
 */
export function ReceiptHeader({
  boxLabel = 'FEE RECEIPT',
  schoolName = 'BALAJI CONVENT & JUNIOR COLLEGE',
  addressLine = 'BUTIBORI, NAGPUR',
  subLine = 'NURSERY TO CLASS 10 (ENGLISH TO SEMI MEDIUM) · JUNIOR COLLEGE (SCIENCE | COMMERCE | ARTS)',
  tagline = 'Shaping Tomorrow, Building Excellence',
  receiptNumber = '',
  dateStr = '',
  academicYear = '',
  qrValue = '',
  qrEnabled = true,
  showBarcode = false,
  compact = false,   // true for A5; slightly smaller logo & type
}) {
  const logoSize = compact ? 40 : 56;
  return (
    <div className="grid grid-cols-12 gap-2 items-start pb-2 border-b-2" style={{ borderColor: 'var(--brand)' }}>
      <div className="col-span-6 flex items-start gap-2">
        <img src={LOGO} alt="Balaji Convent" style={{ width: logoSize, height: logoSize }} className="rounded-full object-cover shrink-0" />
        <div className="leading-tight">
          <div className={`font-black tracking-tight uppercase ${compact ? 'text-[15px]' : 'text-[19px]'}`} style={{ color: 'var(--accent)' }}>{schoolName.split('&')[0]}&</div>
          <div className={`font-black tracking-tight uppercase ${compact ? 'text-[15px]' : 'text-[19px]'}`} style={{ color: 'var(--accent)' }}>{schoolName.split('&')[1] || ''}</div>
          <div className={`font-bold tracking-wide uppercase ${compact ? 'text-[10px]' : 'text-[11px]'} text-slate-800 mt-0.5`}>{addressLine}</div>
          <div className={`${compact ? 'text-[8.5px] leading-tight' : 'text-[9.5px]'} text-slate-600 mt-0.5`}>{subLine}</div>
        </div>
      </div>
      <div className="col-span-3 text-center px-1 border-x" style={{ borderColor: 'var(--line)' }}>
        <div className={`inline-block px-2 py-0.5 font-black tracking-widest ${compact ? 'text-[11px]' : 'text-[13px]'}`} style={{ background: 'var(--brand)', color: 'var(--brand-ink)' }}>{boxLabel}</div>
        <div className={`italic ${compact ? 'text-[9px]' : 'text-[10px]'} text-slate-600 mt-1 leading-tight`}>{tagline}</div>
      </div>
      <div className="col-span-3 text-right text-[10px] leading-tight">
        <Field label="Receipt No." value={<span className="font-mono font-bold text-[12px]" style={{ color: 'var(--accent)' }}>{receiptNumber}</span>} compact={compact} />
        <Field label="Date" value={<span className="font-mono font-semibold">{dateStr}</span>} compact={compact} />
        {academicYear && <Field label="Academic Year" value={<span className="font-mono font-bold">{academicYear}</span>} compact={compact} />}
        {qrEnabled && qrValue && (
          <div className="mt-1 flex justify-end">
            <QRCodeSVG value={qrValue} size={compact ? 44 : 56} level="M" includeMargin={false} />
          </div>
        )}
        {showBarcode && receiptNumber && <Barcode text={receiptNumber} compact={compact} />}
      </div>
    </div>
  );
}

function Field({ label, value, compact }) {
  return (
    <div className={compact ? 'mb-0.5' : 'mb-1'}>
      <div className={`uppercase tracking-widest text-slate-500 font-semibold ${compact ? 'text-[7.5px]' : 'text-[8.5px]'}`}>{label}</div>
      <div className={compact ? 'text-[11px]' : 'text-[12px]'}>{value}</div>
    </div>
  );
}

/** CSS-only barcode strip that scales; visual (non-scannable). */
export function Barcode({ text = '', compact = false }) {
  const bars = [];
  const s = (text || '').toUpperCase();
  for (let i = 0; i < s.length; i++) {
    const c = s.charCodeAt(i);
    for (let b = 0; b < 4; b++) {
      const w = ((c >> b) & 1) ? 2 : 1;
      const black = ((c >> b) & 1) === 1;
      bars.push(<div key={`${i}-${b}`} style={{ width: `${w}px`, height: compact ? 22 : 30, background: black ? '#000' : '#fff', display: 'inline-block' }} />);
      bars.push(<div key={`${i}-${b}g`} style={{ width: '1px', display: 'inline-block' }} />);
    }
  }
  return (
    <div className="mt-1 text-right">
      <div className="inline-flex">{bars}</div>
      <div className={`font-mono tracking-[0.15em] ${compact ? 'text-[8px]' : 'text-[9px]'}`}>{text}</div>
    </div>
  );
}

/** Signature blocks — configurable single-row / 2×2 layout + per-block visibility. */
export function SignatureBlock({
  layout = 'row',                                            // 'row' | 'grid'
  show = { receiver: true, accountant: true, principal: true, director: true },
  labels = { receiver: 'Receiver', accountant: 'Accountant', principal: 'Principal', director: 'Director' },
  compact = false,
}) {
  const items = [
    ['receiver', labels.receiver], ['accountant', labels.accountant],
    ['principal', labels.principal], ['director', labels.director],
  ].filter(([k]) => show[k] !== false);
  if (items.length === 0) return null;
  const cols = layout === 'grid' ? 'grid-cols-2' : `grid-cols-${items.length}`;
  const boxH = compact ? 'h-8' : 'h-10';
  return (
    <div className={`grid ${cols} gap-3 mt-4 pt-2 border-t border-dashed`} style={{ borderColor: 'var(--line)' }}>
      {items.map(([k, label]) => (
        <div key={k} className="text-center">
          <div className={boxH} />
          <div className={`border-t border-slate-500 mx-2 ${compact ? 'text-[9px]' : 'text-[10px]'} pt-0.5 uppercase tracking-widest font-semibold`}>{label}</div>
        </div>
      ))}
    </div>
  );
}

/** Universal footer — remarks + computer-generated note (never removed). */
export function ReceiptFooter({
  remarks = '',
  cashierName = '',
  computerNote = 'This is a computer-generated receipt · No signature required if signature block is hidden.',
  compact = false,
  showSignatures = false,
  signatureLayout = 'row',
  signaturesConfig = { receiver: true, accountant: true, principal: true, director: true },
  signatureLabels,
}) {
  return (
    <div className="mt-2">
      {showSignatures && (
        <SignatureBlock layout={signatureLayout} show={signaturesConfig} labels={signatureLabels} compact={compact} />
      )}
      {remarks && (
        <div className={`${compact ? 'text-[9.5px]' : 'text-[10.5px]'} mt-2 text-slate-700`}>
          <span className="font-semibold uppercase tracking-widest text-slate-500">Remarks:</span> {remarks}
        </div>
      )}
      <div className={`text-center mt-2 pt-1 border-t border-slate-300 ${compact ? 'text-[8.5px]' : 'text-[9.5px]'} text-slate-500`}>
        {computerNote}{cashierName ? ` · Issued by ${cashierName}` : ''}
      </div>
    </div>
  );
}

/** Central "*** CANCELLED ***" / "DUPLICATE" indicators. */
export function StatusRibbons({ status, reprintCount }) {
  return (
    <>
      {status === 'cancelled' && <div className="text-center text-red-600 font-bold text-sm my-1">*** CANCELLED ***</div>}
      {reprintCount > 0 && <div className="text-center text-amber-700 font-semibold text-[10px] my-1">DUPLICATE · Reprint #{reprintCount}</div>}
    </>
  );
}

/** Watermark that shows on-screen AND in print. */
export function Watermark({ text = 'OFFICIAL', enabled = false }) {
  if (!enabled) return null;
  return (
    <div aria-hidden className="absolute inset-0 pointer-events-none flex items-center justify-center" style={{ zIndex: 0 }}>
      <div className="font-heading font-black tracking-tighter" style={{
        transform: 'rotate(-24deg)',
        opacity: 0.06,
        fontSize: 120,
        userSelect: 'none',
        color: 'var(--brand)',
      }}>{text}</div>
    </div>
  );
}
