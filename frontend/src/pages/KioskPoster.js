import React from 'react';
import { PageHeader } from '@/components/Layout';
import { QRCodeSVG } from 'qrcode.react';
import { Printer, Smartphone, ScanLine } from 'lucide-react';

const LOGO = "https://customer-assets-0z36b82j.emergentagent.net/job_finance-hub-school/artifacts/ce0kfh6k_schoolo%20logo.jpeg";

export default function KioskPoster() {
  const base = window.location.origin;

  return (
    <>
      <PageHeader title="Kiosk QR Poster" subtitle="Print an A4 poster for the fee counter and PTM registration desk"
        actions={
          <button data-testid="poster-print" onClick={()=>window.print()} className="h-9 px-3 bg-blue-600 text-white text-sm rounded flex items-center gap-1.5 hover:bg-blue-700 no-print">
            <Printer className="w-4 h-4" /> Print A4
          </button>
        }
      />
      <div className="p-6">
        <div className="print-page bg-white border-8 border-double border-slate-900 mx-auto max-w-2xl p-10 text-center relative overflow-hidden" data-testid="kiosk-poster">
          <div className="absolute top-0 left-0 w-full h-2 bg-slate-900"></div>
          <div className="absolute bottom-0 left-0 w-full h-2 bg-slate-900"></div>

          <img src={LOGO} alt="logo" className="w-28 h-28 rounded-full object-cover mx-auto mb-4 ring-4 ring-slate-900" />
          <div className="font-heading text-3xl font-black tracking-tight uppercase leading-tight">BALAJI CONVENT</div>
          <div className="font-heading text-lg font-bold tracking-wider text-slate-800">& JUNIOR COLLEGE</div>
          <div className="text-[13px] text-slate-600 mb-6 mt-1">BUTIBORI, NAGPUR — 441122</div>

          <div className="inline-flex items-center gap-2 bg-amber-100 border-2 border-amber-500 rounded-full px-4 py-1 text-amber-900 font-bold text-sm mb-6">
            <ScanLine className="w-4 h-4" /> PARENTS — HERE'S A QUICK TIP
          </div>

          <div className="font-heading text-4xl font-black tracking-tight leading-tight mb-2 text-slate-900">
            SCAN THE QR CODE<br/>ON ANY RECEIPT
          </div>
          <div className="text-lg text-slate-700 mb-8">to instantly view your child's <span className="font-bold underline decoration-amber-500 decoration-4 underline-offset-4">complete fee ledger</span></div>

          <div className="grid grid-cols-3 gap-4 items-center bg-slate-50 border-2 border-slate-300 rounded-lg p-6 my-6">
            <div className="text-center">
              <div className="w-16 h-16 bg-slate-900 text-white rounded-full flex items-center justify-center mx-auto mb-2"><Smartphone className="w-8 h-8" /></div>
              <div className="text-[11px] font-bold uppercase tracking-widest text-slate-700">1. Open Camera</div>
              <div className="text-[11px] text-slate-500 mt-1">on your phone</div>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 bg-slate-900 text-white rounded-full flex items-center justify-center mx-auto mb-2"><ScanLine className="w-8 h-8" /></div>
              <div className="text-[11px] font-bold uppercase tracking-widest text-slate-700">2. Point at QR</div>
              <div className="text-[11px] text-slate-500 mt-1">on the receipt</div>
            </div>
            <div className="text-center">
              <div className="w-16 h-16 bg-emerald-600 text-white rounded-full flex items-center justify-center mx-auto mb-2 font-bold text-2xl">✓</div>
              <div className="text-[11px] font-bold uppercase tracking-widest text-slate-700">3. Tap the link</div>
              <div className="text-[11px] text-slate-500 mt-1">see your ledger</div>
            </div>
          </div>

          <div className="bg-slate-900 text-white rounded-lg p-6 mt-4">
            <div className="text-[11px] uppercase tracking-widest text-slate-300">Sample QR — Every receipt has its own</div>
            <div className="flex justify-center my-3 bg-white rounded p-3 mx-auto w-fit">
              <QRCodeSVG value={`${base}/lookup/BC2026-000123`} size={140} level="M" includeMargin={false} />
            </div>
            <div className="text-[13px] text-slate-200 mt-2">100% Safe · View-Only · No login required</div>
          </div>

          <div className="text-[13px] text-slate-700 mt-6 italic">Any issue? Please visit the school office — 9:00 AM to 3:00 PM (Mon–Sat)</div>
          <div className="text-[11px] text-slate-500 mt-4 tracking-widest">SHAPING TOMORROW · BUILDING EXCELLENCE</div>
        </div>
      </div>
    </>
  );
}
