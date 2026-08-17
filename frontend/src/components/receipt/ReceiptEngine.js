import React, { useMemo, useRef, useState } from 'react';
import ReceiptFrame from './ReceiptFrame';
import ReceiptToolbar from './ReceiptToolbar';
import { ReceiptHeader, ReceiptFooter, StatusRibbons, Watermark } from './ReceiptPrimitives';
import { paperOptions, DEFAULT_PAPER } from './PaperSizes';
import FeeReceiptBody from './templates/FeeReceiptBody';
import DebitVoucherBody from './templates/DebitVoucherBody';
import MoneyReceiptBody from './templates/MoneyReceiptBody';
import BusReceiptBody from './templates/BusReceiptBody';

/**
 * ReceiptEngine — the single component every printable document uses.
 *
 * Composes:
 *   ReceiptFrame  (paper size + theme + margins + @page CSS)
 *     ▸ Watermark
 *     ▸ ReceiptHeader (logo + school name + tagline + receipt no + QR/barcode)
 *     ▸ StatusRibbons (Cancelled / Duplicate)
 *     ▸ <body>       (delegated to a template component)
 *     ▸ ReceiptFooter (signatures + remarks + computer-generated line)
 *
 * The engine also renders the toolbar (Print / PDF / PNG / JPEG / SVG / Email PDF)
 * and paper-size + theme pickers, so every page that plugs into the engine gets
 * multi-format export "for free".
 *
 * Props:
 *   r            — the receipt object
 *   receiptType  — the receipt_type record (paper_size, theme, watermark…)
 *   onPrint      — optional pre-print hook (e.g. increment reprint count)
 *   extraActions — extra buttons on the toolbar (Cancel, Back…)
 *   showControls — set false to hide the "Paper size / Theme" pickers
 */
export default function ReceiptEngine({
  r, receiptType,
  onPrint, extraActions = null, showControls = true,
}) {
  const nodeRef = useRef(null);
  const [paper, setPaper] = useState(receiptType?.paper_size || DEFAULT_PAPER);
  const [theme, setTheme] = useState(receiptType?.theme || 'bw');
  const [twoUp, setTwoUp] = useState(false);
  const boxLabel = boxLabelFor(r, receiptType);
  const isCompact = paper === 'A5' || paper === 'THERMAL80';
  const filename = safeFilename(r.number || `receipt-${r.id?.slice(0,8)}`);
  const marginsMm = paperMargins(paper, receiptType);

  const Body = useMemo(() => renderBody(r, isCompact), [r, isCompact]);

  const [scale, setScale] = useState(1);
  // Auto-scale preview to fit ~700px width
  const autoScale = useMemo(() => {
    // A5 portrait = 148mm ≈ 559px; A4 portrait = 210mm ≈ 793px; landscape wider.
    const previewMax = 700;
    const pxPerMm = 96 / 25.4;
    const paperWidthPx = paperWidthMm(paper) * pxPerMm;
    return Math.min(1, previewMax / paperWidthPx);
  }, [paper]);

  const effectiveScale = scale === 'auto' ? autoScale : scale;

  const showBarcode = !!receiptType?.barcode_enabled;
  const qrEnabled = receiptType ? receiptType.qr_enabled !== false : true;
  const wmEnabled = !!receiptType?.watermark_enabled;
  const wmText = receiptType?.watermark_text || 'OFFICIAL';
  const showSigs = receiptType ? receiptType.signature_area_enabled !== false : true;
  const sigLayout = receiptType?.signature_layout || (r.receipt_type === 'debit_voucher' ? 'row' : 'row');
  const sigConfig = receiptType?.signatures_config || (r.receipt_type === 'debit_voucher'
    ? { receiver: true, accountant: true, principal: true, director: true }
    : { receiver: true, accountant: false, principal: false, director: true });

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="bg-white border border-slate-200 rounded p-3 flex items-center justify-between flex-wrap gap-3 no-print">
        <div className="flex items-center gap-2 flex-wrap">
          {showControls && (
            <>
              <label className="text-[11px] uppercase tracking-widest text-slate-500 font-semibold">Paper</label>
              <select data-testid="receipt-paper" value={paper} onChange={(e) => setPaper(e.target.value)}
                className="h-9 px-2 border border-slate-300 rounded text-sm bg-white">
                {paperOptions().map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <label className="text-[11px] uppercase tracking-widest text-slate-500 font-semibold ml-3">Theme</label>
              <select data-testid="receipt-theme" value={theme} onChange={(e) => setTheme(e.target.value)}
                className="h-9 px-2 border border-slate-300 rounded text-sm bg-white">
                <option value="bw">Classic B/W</option>
                <option value="color">Balaji Colored</option>
              </select>
              <label className="text-[11px] uppercase tracking-widest text-slate-500 font-semibold ml-3">Zoom</label>
              <select value={scale} onChange={(e) => setScale(e.target.value === 'auto' ? 'auto' : Number(e.target.value))}
                className="h-9 px-2 border border-slate-300 rounded text-sm bg-white">
                <option value="auto">Fit</option>
                {[0.5, 0.75, 1, 1.25, 1.5].map(v => <option key={v} value={v}>{`${Math.round(v*100)}%`}</option>)}
              </select>
            </>
          )}
        </div>
        <ReceiptToolbar
          nodeRef={nodeRef}
          filename={filename}
          paper={paper}
          onPrint={onPrint}
          twoUp={twoUp}
          onTwoUp={() => setTwoUp(v => !v)}
          extraActions={extraActions}
        />
      </div>

      {/* Preview canvas — centred inside a light backdrop */}
      <div className="flex justify-center bg-slate-100 rounded p-6 overflow-auto">
        <ReceiptFrame
          paper={paper}
          theme={theme}
          marginsMm={marginsMm}
          scale={effectiveScale}
          innerRef={nodeRef}
        >
          <Watermark text={wmText} enabled={wmEnabled} />

          <ReceiptHeader
            boxLabel={boxLabel}
            receiptNumber={r.number}
            dateStr={new Date(r.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
            academicYear={r.academic_year}
            qrValue={`${window.location.origin}/lookup/${r.number}`}
            qrEnabled={qrEnabled}
            showBarcode={showBarcode}
            compact={isCompact}
          />

          <StatusRibbons status={r.status} reprintCount={r.reprint_count} />

          {Body}

          <ReceiptFooter
            remarks={r.remarks}
            cashierName={r.cashier_name}
            computerNote={receiptType?.computer_generated_note || 'This is a computer-generated receipt.'}
            compact={isCompact}
            showSignatures={showSigs}
            signatureLayout={sigLayout}
            signaturesConfig={sigConfig}
          />

          {twoUp && (
            <>
              <div className="text-center text-[9px] text-slate-500 tracking-widest my-3 border-t-2 border-dashed border-slate-400 pt-1">— — — — — CUT HERE · Office Copy below — — — — —</div>
              <ReceiptHeader
                boxLabel={boxLabel} receiptNumber={r.number}
                dateStr={new Date(r.created_at).toLocaleDateString('en-IN')}
                academicYear={r.academic_year}
                qrValue={`${window.location.origin}/lookup/${r.number}`}
                qrEnabled={qrEnabled} showBarcode={showBarcode} compact={isCompact}
              />
              {Body}
              <ReceiptFooter
                remarks={r.remarks} cashierName={r.cashier_name}
                computerNote={receiptType?.computer_generated_note || 'This is a computer-generated receipt.'}
                compact={isCompact} showSignatures={showSigs}
                signatureLayout={sigLayout} signaturesConfig={sigConfig}
              />
            </>
          )}
        </ReceiptFrame>
      </div>
    </div>
  );
}

/* -------------------- helpers -------------------- */

function renderBody(r, compact) {
  switch (r.receipt_type) {
    case 'debit_voucher':          return <DebitVoucherBody r={r} compact={compact} />;
    case 'bus':                    return <BusReceiptBody r={r} compact={compact} />;
    case 'refund':
    case 'general_money':
    case 'general_collection':     return <MoneyReceiptBody r={r} compact={compact} />;
    default:                       return <FeeReceiptBody r={r} compact={compact} />;
  }
}

function boxLabelFor(r, rt) {
  if (rt?.header_text) return rt.header_text;
  switch (r.receipt_type) {
    case 'debit_voucher':       return 'DEBIT VOUCHER';
    case 'bus':                 return 'BUS FEE RECEIPT';
    case 'refund':              return 'REFUND RECEIPT';
    case 'admission':           return 'ADMISSION RECEIPT';
    case 'general_money':
    case 'general_collection':  return 'MONEY RECEIPT';
    default:                    return 'FEE RECEIPT';
  }
}

function paperMargins(paper, rt) {
  const dflt = paper === 'A5' || paper === 'THERMAL80'
    ? { top: 6, right: 6, bottom: 6, left: 6 }
    : { top: 10, right: 10, bottom: 10, left: 10 };
  return { ...dflt, ...(rt?.margins_mm || {}) };
}

function paperWidthMm(paper) {
  return {
    A5: 148, A5_LANDSCAPE: 210, A4: 210, A4_LANDSCAPE: 297,
    LEGAL: 216, LETTER: 216, THERMAL80: 80,
  }[paper] || 148;
}

function safeFilename(s) {
  return String(s || 'receipt').replace(/[^\w.-]+/g, '-');
}
