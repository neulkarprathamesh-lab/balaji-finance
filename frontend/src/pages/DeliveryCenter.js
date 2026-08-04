import React, { useEffect, useState } from 'react';
import api from '@/lib/api';
import { PageHeader } from '@/components/Layout';
import { toast } from 'sonner';
import {
  Download, Package, Server, Database, Settings2, Receipt, BookOpen,
  History, ShieldCheck, RefreshCw, ExternalLink, FileText, CheckCircle2
} from 'lucide-react';

const ICONS = {
  package: Package, server: Server, database: Database, settings: Settings2,
  receipt: Receipt, book: BookOpen, history: History,
};

function useAdminPin() {
  const [pin, setPin] = useState('');
  const ask = () => {
    const p = window.prompt('Administrator PIN required for this download:');
    if (p) setPin(p);
    return p;
  };
  return { pin, ask };
}

async function downloadWithPin(endpoint, filename, pin) {
  const url = `${process.env.REACT_APP_BACKEND_URL}${endpoint}`;
  const r = await fetch(url, {
    method: 'GET',
    credentials: 'include',
    headers: pin ? { 'X-Admin-Pin': pin } : {},
  });
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  const blob = await r.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(a.href);
}

export default function DeliveryCenter() {
  const [manifest, setManifest] = useState(null);
  const [busy, setBusy] = useState(null);
  const { ask } = useAdminPin();

  const load = () => api.get('/deliverables/manifest').then(r => setManifest(r.data));
  useEffect(() => { load(); }, []);

  const doDownload = async (item) => {
    setBusy(item.label);
    try {
      if (item.route) {
        window.open(item.route, '_blank');
      } else if (item.endpoint) {
        const filename = item.label.replace(/[^a-z0-9-]+/gi, '_').toLowerCase() + '.dat';
        const needsPin = item.endpoint.includes('/config/export') || item.endpoint.includes('/config/backup') || item.endpoint.includes('/deliverables/');
        const pin = needsPin ? ask() : null;
        // Detect proper extension by hint
        const fname =
          item.endpoint.includes('receipt-types') ? 'receipt-types-v1.0.json' :
          item.endpoint.includes('license')       ? 'LICENSE_AND_OWNERSHIP.md' :
          item.endpoint.includes('release-notes') ? 'RELEASE_NOTES_v1.0.md' :
          item.endpoint.includes('config/export') ? `balaji-config-${new Date().toISOString().slice(0,10)}.zip` :
          filename;
        await downloadWithPin(item.endpoint, fname, pin);
        toast.success(`Downloaded ${fname}`);
      }
    } catch (e) {
      toast.error(e.message || 'Download failed');
    }
    setBusy(null);
  };

  if (!manifest) return <div className="p-8 text-sm text-slate-500">Loading Delivery Center…</div>;

  return (
    <>
      <PageHeader
        title="Final Delivery Center"
        subtitle={`Version ${manifest.app_version} · Schema v${manifest.database_version} · Generated ${new Date(manifest.generated_at).toLocaleString('en-IN')}`}
        actions={
          <button onClick={load} className="h-9 px-3 border border-slate-300 rounded text-sm hover:bg-white flex items-center gap-1.5" data-testid="dc-refresh">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
        }
      />
      <div className="p-6 space-y-6" data-testid="delivery-center">
        <div className="p-4 rounded-xl bg-gradient-to-r from-emerald-50 to-blue-50 border border-emerald-200 flex items-start gap-3">
          <CheckCircle2 className="w-6 h-6 text-emerald-600 shrink-0 mt-0.5" />
          <div>
            <div className="font-heading font-semibold text-emerald-900">Version 1.0 is production-ready</div>
            <div className="text-[13px] text-emerald-800 mt-0.5">
              This is the day-to-day download hub for the school — configuration exports, the latest database backup, and the ownership documents.
              The <strong>complete source-code ZIP is delivered separately</strong> for you to store safely on the Main Server + an external drive; it is intentionally not exposed inside the running app.
            </div>
          </div>
        </div>

        {manifest.sections.map((section) => {
          const Icon = ICONS[section.icon] || Package;
          return (
            <section key={section.title} className="bg-white rounded-xl border border-slate-200 overflow-hidden" data-testid={`dc-section-${section.title.replace(/\s+/g,'-').toLowerCase()}`}>
              <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2 bg-slate-50">
                <Icon className="w-4 h-4 text-slate-500" />
                <h2 className="text-sm font-semibold text-slate-800">{section.title}</h2>
              </div>
              <div className="divide-y divide-slate-100">
                {section.items.map((item, idx) => (
                  <div key={idx} className="px-4 py-3 flex items-start justify-between gap-4">
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-slate-900">{item.label}</div>
                      {item.note && <div className="text-[12px] text-slate-500 mt-0.5">{item.note}</div>}
                      <div className="text-[11px] text-slate-400 mt-1 flex items-center gap-2 flex-wrap">
                        {item.size_mb !== null && item.size_mb !== undefined && <span>{item.size_mb} MB</span>}
                        {item.modified_at && <span>· updated {new Date(item.modified_at).toLocaleDateString('en-IN')}</span>}
                        {item.method && <span>· HTTP {item.method}</span>}
                      </div>
                    </div>
                    {item.available === false ? (
                      <span className="text-[11px] uppercase font-semibold text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1">Pending</span>
                    ) : item.route ? (
                      <a
                        href={item.route}
                        target="_blank" rel="noreferrer"
                        className="h-9 px-3 bg-slate-900 hover:bg-slate-800 text-white rounded text-sm font-semibold inline-flex items-center gap-1.5"
                        data-testid={`dc-download-${section.title.replace(/\s+/g,'-').toLowerCase()}-${idx}`}
                      >
                        <ExternalLink className="w-4 h-4" /> Download
                      </a>
                    ) : (
                      <button
                        onClick={() => doDownload(item)}
                        disabled={busy === item.label}
                        className="h-9 px-3 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded text-sm font-semibold inline-flex items-center gap-1.5"
                        data-testid={`dc-download-${section.title.replace(/\s+/g,'-').toLowerCase()}-${idx}`}
                      >
                        {busy === item.label ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
                        {busy === item.label ? 'Preparing…' : 'Download'}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </section>
          );
        })}

        <section className="bg-slate-900 text-slate-100 rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <h3 className="text-sm font-semibold">Ownership & Freedom</h3>
          </div>
          <ul className="text-[13px] text-slate-300 space-y-1 leading-relaxed">
            <li>· This software is the exclusive property of Balaji Convent & Junior College upon final payment.</li>
            <li>· No hidden dependencies, license locks, activation servers, subscription requirements or kill switches.</li>
            <li>· Every source file ships in its readable form. No obfuscation.</li>
            <li>· Balaji Convent can maintain, modify, enhance, rebuild, or continue development internally or through any third-party developer without permission.</li>
          </ul>
          <a
            href="#" onClick={(e) => { e.preventDefault(); doDownload({ label: 'License & Ownership', endpoint: '/api/deliverables/license' }); }}
            className="mt-3 inline-flex items-center gap-1.5 text-sm text-emerald-300 hover:text-emerald-200"
            data-testid="dc-license"
          >
            <FileText className="w-4 h-4" /> Download the signed License & Ownership document →
          </a>
        </section>
      </div>
    </>
  );
}
