import React, { useState, useRef } from 'react';
import * as XLSX from 'xlsx';
import api from '@/lib/api';
import { PageHeader } from '@/components/Layout';
import { toast } from 'sonner';
import { Download, Upload, FileSpreadsheet, CheckCircle2, XCircle, AlertTriangle, RefreshCw } from 'lucide-react';

const TEMPLATE_HEADERS = ['admission_no', 'name', 'department_code', 'class_name', 'guardian_name', 'guardian_mobile', 'address', 'medium'];
const SAMPLE_ROWS = [
  ['BC-EP-101', 'Aarav Sharma', 'EP', 'Class 3', 'Rajesh Sharma', '9876500001', 'Butibori, Nagpur', 'English'],
  ['BC-MP-045', 'Rohan Deshmukh', 'MP', 'Class 4', 'Prakash Deshmukh', '9876500003', 'Butibori', 'Semi-English'],
  ['BC-JC-012', 'Anjali Kulkarni', 'JC', 'Class 12 - Science', 'Vinod Kulkarni', '9876500006', 'Butibori', 'Junior College'],
];

const BATCH_SIZE = 10;

export default function ImportExcel() {
  const fileRef = useRef();
  const [rows, setRows] = useState([]);
  const [progress, setProgress] = useState({ done: 0, added: 0, skipped: 0, errors: [], current: null, running: false, finished: false });
  const [filename, setFilename] = useState('');

  const downloadTemplate = () => {
    const ws = XLSX.utils.aoa_to_sheet([TEMPLATE_HEADERS, ...SAMPLE_ROWS]);
    ws['!cols'] = TEMPLATE_HEADERS.map(() => ({ wch: 20 }));
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Students');
    XLSX.writeFile(wb, 'balaji_students_template.xlsx');
    toast.success('Template downloaded — fill it in Excel then upload here');
  };

  const onFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setFilename(file.name);
    const buf = await file.arrayBuffer();
    const wb = XLSX.read(buf, { type: 'array' });
    const sheet = wb.Sheets[wb.SheetNames[0]];
    const parsed = XLSX.utils.sheet_to_json(sheet, { defval: '', raw: false });
    // Normalize header keys to snake_case
    const normalized = parsed.map(r => {
      const o = {};
      for (const k of Object.keys(r)) o[k.trim().toLowerCase().replace(/\s+/g, '_')] = String(r[k]).trim();
      return o;
    }).filter(r => r.admission_no || r.name);
    setRows(normalized);
    setProgress({ done: 0, added: 0, skipped: 0, errors: [], current: null, running: false, finished: false });
    toast.success(`✓ Loaded ${normalized.length} rows from ${file.name}`);
  };

  const startImport = async () => {
    if (!rows.length) return toast.error('Load an Excel file first');
    setProgress(p => ({ ...p, running: true, finished: false }));
    let added = 0, skipped = 0; const errs = [];
    for (let i = 0; i < rows.length; i += BATCH_SIZE) {
      const batch = rows.slice(i, i + BATCH_SIZE);
      const current = batch[0]?.name || batch[0]?.admission_no || '—';
      setProgress(p => ({ ...p, current: `${current} (row ${i+1})`, done: i }));
      try {
        const { data } = await api.post('/students/bulk-import', { rows: batch });
        added += data.created; skipped += data.skipped;
        for (const e of (data.errors || [])) errs.push({ ...e, row: i + e.row });
      } catch (ex) {
        for (let j = 0; j < batch.length; j++) errs.push({ row: i + j + 1, error: ex?.response?.data?.detail || 'Batch failed', data: batch[j] });
      }
      setProgress(p => ({ ...p, added, skipped, errors: errs, done: Math.min(i + BATCH_SIZE, rows.length) }));
      await new Promise(r => setTimeout(r, 60)); // let UI paint
    }
    setProgress(p => ({ ...p, running: false, finished: true, current: null, done: rows.length }));
    toast.success(`✓ Import complete — ${added} added, ${skipped} skipped, ${errs.length} errors`);
  };

  const downloadErrors = () => {
    if (!progress.errors.length) return;
    const rows = [['Row', 'Error', 'admission_no', 'name', 'department_code', 'class_name']];
    for (const e of progress.errors) rows.push([e.row, e.error, e.data?.admission_no || '', e.data?.name || '', e.data?.department_code || '', e.data?.class_name || '']);
    const ws = XLSX.utils.aoa_to_sheet(rows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Errors');
    XLSX.writeFile(wb, `import_errors_${Date.now()}.xlsx`);
  };

  const reset = () => { setRows([]); setFilename(''); setProgress({ done: 0, added: 0, skipped: 0, errors: [], current: null, running: false, finished: false }); if (fileRef.current) fileRef.current.value = ''; };

  const pct = rows.length ? Math.round((progress.done / rows.length) * 100) : 0;
  const remaining = rows.length - progress.done;

  return (
    <>
      <PageHeader title="Excel Import — Students" subtitle="Download the ready-made template, fill it in Excel, then upload here with live progress" />
      <div className="p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Step 1: Template */}
        <div className="bg-white border border-slate-200 rounded p-5">
          <div className="text-[11px] uppercase tracking-widest text-slate-500">Step 1</div>
          <h3 className="font-heading font-semibold text-lg mt-1">Download Template</h3>
          <p className="text-[13px] text-slate-600 mt-2">A ready-to-fill Excel with the exact column headers we need and 3 sample rows.</p>
          <button data-testid="tpl-download" onClick={downloadTemplate} className="mt-4 h-10 px-4 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-sm w-full flex items-center justify-center gap-2">
            <Download className="w-4 h-4" /> Download Template (.xlsx)
          </button>
          <div className="text-[11px] text-slate-500 mt-3">Required columns: <span className="font-mono">admission_no, name, department_code, class_name</span></div>
          <div className="text-[11px] text-slate-500">Optional: <span className="font-mono">guardian_name, guardian_mobile, address, medium</span></div>
          <div className="text-[11px] text-slate-500 mt-2">Dept codes: EP (English Primary) · MP (Marathi Primary) · SEC (Secondary) · JC (Junior College)</div>
        </div>

        {/* Step 2: Upload */}
        <div className="bg-white border border-slate-200 rounded p-5">
          <div className="text-[11px] uppercase tracking-widest text-slate-500">Step 2</div>
          <h3 className="font-heading font-semibold text-lg mt-1">Upload Filled Excel</h3>
          <p className="text-[13px] text-slate-600 mt-2">Accepts .xlsx, .xls or .csv. Parsed instantly in your browser.</p>
          <label className="mt-4 h-10 px-4 border-2 border-dashed border-slate-300 hover:border-slate-500 rounded text-sm w-full flex items-center justify-center gap-2 cursor-pointer text-slate-700">
            <Upload className="w-4 h-4" />
            <span>{filename || 'Choose file…'}</span>
            <input data-testid="excel-upload" ref={fileRef} type="file" accept=".xlsx,.xls,.csv" onChange={onFile} className="hidden" />
          </label>
          {rows.length > 0 && (
            <div className="mt-3 p-3 bg-slate-50 border border-slate-200 rounded text-sm">
              <FileSpreadsheet className="w-4 h-4 inline mr-1 text-slate-500" />
              <b>{rows.length}</b> rows detected · ready to import
            </div>
          )}
        </div>

        {/* Step 3: Progress + Import */}
        <div className="bg-white border border-slate-200 rounded p-5">
          <div className="text-[11px] uppercase tracking-widest text-slate-500">Step 3</div>
          <h3 className="font-heading font-semibold text-lg mt-1">Import & Track Progress</h3>
          <p className="text-[13px] text-slate-600 mt-2">Students are added in batches of {BATCH_SIZE}. You'll see who's being processed live.</p>
          {!progress.finished ? (
            <button data-testid="import-start" onClick={startImport} disabled={progress.running || !rows.length} className="mt-4 h-10 px-4 bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white rounded text-sm w-full flex items-center justify-center gap-2">
              {progress.running ? <><span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin"></span> Importing…</> : <><Upload className="w-4 h-4" /> Start Import</>}
            </button>
          ) : (
            <button data-testid="import-reset" onClick={reset} className="mt-4 h-10 px-4 border border-slate-300 rounded text-sm w-full flex items-center justify-center gap-2 hover:bg-slate-50">
              <RefreshCw className="w-4 h-4" /> Import Another File
            </button>
          )}
        </div>

        {/* Progress panel — spans full width */}
        {(progress.running || progress.finished) && (
          <div className="lg:col-span-3 bg-white border-2 border-blue-200 rounded p-5">
            <div className="flex items-baseline justify-between mb-3">
              <h3 className="font-heading font-semibold text-lg">{progress.finished ? '✓ Import Complete' : 'Importing…'}</h3>
              <div className="text-[13px] text-slate-500 tabular font-mono">{progress.done} / {rows.length} · {pct}%</div>
            </div>

            <div className="w-full h-3 bg-slate-100 rounded-full overflow-hidden mb-4">
              <div className="h-full bg-gradient-to-r from-blue-500 to-emerald-500 transition-all duration-300" style={{ width: `${pct}%` }} />
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
              <Stat icon={FileSpreadsheet} label="Total in Excel" value={rows.length} tone="text-slate-900" />
              <Stat icon={CheckCircle2} label="Added" value={progress.added} tone="text-emerald-700" />
              <Stat icon={AlertTriangle} label="Skipped (duplicates)" value={progress.skipped} tone="text-amber-700" />
              <Stat icon={XCircle} label="Errors" value={progress.errors.length} tone="text-red-700" />
            </div>

            <div className="grid grid-cols-2 gap-3 mb-3 text-sm">
              <div className="bg-slate-50 border border-slate-200 rounded p-3">
                <div className="text-[10px] uppercase tracking-widest text-slate-500">Currently processing</div>
                <div className="font-semibold text-slate-900 mt-0.5">{progress.current || (progress.finished ? '— Done —' : '…')}</div>
              </div>
              <div className="bg-slate-50 border border-slate-200 rounded p-3">
                <div className="text-[10px] uppercase tracking-widest text-slate-500">Remaining</div>
                <div className="font-heading text-xl font-semibold tabular text-slate-900">{remaining}</div>
              </div>
            </div>

            {progress.errors.length > 0 && (
              <div className="border border-red-200 bg-red-50 rounded p-3 mt-3">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-sm text-red-800 font-semibold flex items-center gap-1.5"><XCircle className="w-4 h-4" /> {progress.errors.length} row{progress.errors.length===1?'':'s'} had errors</div>
                  <button data-testid="err-download" onClick={downloadErrors} className="text-xs h-8 px-3 bg-red-600 hover:bg-red-700 text-white rounded flex items-center gap-1.5"><Download className="w-3.5 h-3.5" /> Download Error Report</button>
                </div>
                <div className="max-h-40 overflow-y-auto text-[12px] space-y-0.5">
                  {progress.errors.slice(0, 20).map((e, i) => (
                    <div key={i} className="text-red-800"><span className="font-mono">Row {e.row}:</span> {e.error} <span className="text-red-500">— {e.data?.admission_no || ''} {e.data?.name || ''}</span></div>
                  ))}
                  {progress.errors.length > 20 && <div className="text-red-600 italic mt-1">…and {progress.errors.length - 20} more — download the report to see all.</div>}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </>
  );
}

const Stat = ({ icon: Icon, label, value, tone }) => (
  <div className="bg-white border border-slate-200 rounded p-3">
    <div className="flex justify-between items-center mb-1">
      <div className="text-[10px] uppercase tracking-widest text-slate-500">{label}</div>
      <Icon className="w-4 h-4 text-slate-400" strokeWidth={1.75} />
    </div>
    <div className={`font-heading text-2xl font-bold tabular ${tone}`}>{value}</div>
  </div>
);
