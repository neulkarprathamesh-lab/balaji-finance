import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { PageHeader } from '@/components/Layout';
import AdminPinPrompt from '@/components/AdminPinPrompt';
import { Download, Upload, Shield, PackageOpen, CheckCircle2, AlertTriangle } from 'lucide-react';

const BACKEND = process.env.REACT_APP_BACKEND_URL;

export default function ConfigExportImport() {
  const [prompt, setPrompt] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [version, setVersion] = useState(null);
  const [replace, setReplace] = useState(false);
  useEffect(() => { api.get('/version').then(r => setVersion(r.data)).catch(()=>{}); }, []);

  const doExport = () => setPrompt({
    mode: 'pin', title: 'Export School Configuration',
    message: 'This will download a ZIP with all receipt types, departments, classes, fee heads, fee structures, bus routes and settings.',
    onOk: async (headers) => {
      try {
        const token = localStorage.getItem('bc.token');
        const r = await fetch(`${BACKEND}/api/config/export`, {
          headers: { 'Authorization': `Bearer ${token}`, ...headers }
        });
        if (!r.ok) throw new Error('Export failed');
        const blob = await r.blob();
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `balaji-config-${new Date().toISOString().slice(0,10)}.zip`;
        document.body.appendChild(a); a.click(); a.remove();
        toast.success('Configuration downloaded');
      } catch (e) { toast.error('Export failed'); }
    }
  });

  const doImport = (file) => setPrompt({
    mode: 'dual',
    title: 'Import School Configuration',
    message: 'This is a HIGH-RISK action that will change master data. Enter your PIN and Admin Password (dual authorisation).',
    onOk: async (headers) => {
      const token = localStorage.getItem('bc.token');
      const fd = new FormData();
      fd.append('file', file);
      try {
        const r = await fetch(`${BACKEND}/api/config/import?replace=${replace}`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}`, ...headers },
          body: fd,
        });
        const j = await r.json();
        if (!r.ok) throw new Error(j.detail || 'Import failed');
        setImportResult(j);
        toast.success('Configuration imported');
      } catch (e) { toast.error(e.message || 'Import failed'); }
    }
  });

  return (
    <>
      <PageHeader title="Configuration Export / Import"
        subtitle="Move school setup between PCs — receipt types, fees, departments, classes, settings"
      />
      <div className="p-6 space-y-4 max-w-4xl">
        {version && (
          <div className="bg-slate-900 text-white rounded-lg p-4 flex items-center justify-between">
            <div>
              <div className="text-[10px] uppercase tracking-widest text-slate-400 font-bold">Current Version</div>
              <div className="font-heading text-2xl font-bold" data-testid="cfg-version">{version.app_version}</div>
            </div>
            <div className="grid grid-cols-3 gap-4 text-[11px] text-slate-300">
              <div><div className="text-slate-500 uppercase tracking-widest text-[9px]">Database</div><div className="font-mono font-bold text-white">v{version.database_version}</div></div>
              <div><div className="text-slate-500 uppercase tracking-widest text-[9px]">Templates</div><div className="font-mono font-bold text-white">v{version.receipt_template_version}</div></div>
              <div><div className="text-slate-500 uppercase tracking-widest text-[9px]">Build</div><div className="font-mono font-bold text-white">{version.build_date}</div></div>
            </div>
          </div>
        )}

        {/* Export card */}
        <div className="bg-white border border-slate-200 rounded-lg p-5 flex items-start gap-4">
          <div className="w-12 h-12 rounded-lg bg-emerald-100 text-emerald-700 flex items-center justify-center flex-shrink-0"><Download className="w-6 h-6" /></div>
          <div className="flex-1">
            <div className="font-heading font-semibold text-lg">Export Configuration</div>
            <div className="text-[12px] text-slate-600 mt-0.5">Downloads a portable ZIP with receipt types, departments, classes, fee heads & structures, settings, bus routes and users (passwords excluded).</div>
            <button data-testid="cfg-export" onClick={doExport} className="mt-3 h-9 px-4 bg-emerald-600 hover:bg-emerald-700 text-white rounded text-sm flex items-center gap-1.5"><Download className="w-4 h-4" /> Export ZIP (requires PIN)</button>
          </div>
        </div>

        {/* Import card */}
        <div className="bg-white border border-slate-200 rounded-lg p-5 flex items-start gap-4">
          <div className="w-12 h-12 rounded-lg bg-blue-100 text-blue-700 flex items-center justify-center flex-shrink-0"><Upload className="w-6 h-6" /></div>
          <div className="flex-1">
            <div className="font-heading font-semibold text-lg">Import Configuration</div>
            <div className="text-[12px] text-slate-600 mt-0.5">Upload a configuration ZIP exported from another Balaji instance. Perfect for cloning a school's setup to a new site.</div>
            <div className="mt-3 flex items-center gap-4">
              <label className="inline-flex items-center gap-2 text-[12px] text-slate-700 bg-slate-50 border border-slate-200 rounded px-3 py-1.5">
                <input type="checkbox" checked={replace} onChange={e=>setReplace(e.target.checked)} />
                <b>Replace mode</b> (wipes existing rows first — DANGER)
              </label>
              <label className="inline-flex items-center gap-2">
                <input type="file" accept=".zip" data-testid="cfg-file" onChange={e => e.target.files?.[0] && doImport(e.target.files[0])} className="text-[12px]" />
              </label>
            </div>
            <div className="mt-2 text-[11px] text-amber-800 bg-amber-50 border border-amber-200 rounded px-2 py-1 inline-flex items-center gap-1.5">
              <Shield className="w-3 h-3" /> Dual authorisation required — Admin PIN + Password.
            </div>
          </div>
        </div>

        {importResult && (
          <div className="bg-white border-2 border-emerald-500 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              <div className="font-heading font-semibold">Import Summary</div>
            </div>
            <div className="text-[11px] text-slate-500 mb-2">From: {importResult.manifest?.exported_by} on {importResult.manifest?.exported_at?.slice(0,10)} · App v{importResult.manifest?.app_version} · Mode: {importResult.replace_mode ? 'REPLACE' : 'MERGE'}</div>
            <table className="w-full text-sm border border-slate-200">
              <thead className="bg-slate-50 text-[11px] uppercase text-slate-600"><tr className="text-left"><th className="px-2 py-1.5">Collection</th><th className="px-2 py-1.5 text-right">Added</th><th className="px-2 py-1.5 text-right">Updated</th><th className="px-2 py-1.5 text-right">Total in File</th></tr></thead>
              <tbody>{Object.entries(importResult.summary?.imported || {}).map(([k, v]) => (
                <tr key={k} className="border-t border-slate-100">
                  <td className="px-2 py-1.5">{k}</td>
                  <td className="px-2 py-1.5 text-right text-emerald-700 font-mono">{v.added}</td>
                  <td className="px-2 py-1.5 text-right text-blue-700 font-mono">{v.updated}</td>
                  <td className="px-2 py-1.5 text-right font-mono">{v.total_in_file}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </div>
      <AdminPinPrompt prompt={prompt} onClose={()=>setPrompt(null)} />
    </>
  );
}
