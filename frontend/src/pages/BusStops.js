import React, { useEffect, useState } from 'react';
import api from '@/lib/api';
import { PageHeader, inr } from '@/components/Layout';
import { toast } from 'sonner';
import { Plus, Bus, Pencil, Trash2, PowerOff, Power, Search } from 'lucide-react';
import { useAuth } from '@/context/AuthContext';

/**
 * Bus Stop Manager — Administrator page under Bus Routes.
 * Add / edit / deactivate stops and update fares for future academic years.
 * Stops used by any student cannot be deleted (must set inactive instead).
 */
export default function BusStops() {
  const { user } = useAuth();
  const canEdit = ['administrator', 'manager', 'accountant'].includes(user?.role);
  const canDelete = user?.role === 'administrator';
  const [stops, setStops] = useState([]);
  const [q, setQ] = useState('');
  const [editing, setEditing] = useState(null); // full stop being edited (null = closed)
  const [creating, setCreating] = useState(false);

  const load = () => api.get('/bus-stops').then(r => setStops(r.data));
  useEffect(() => { load(); }, []);

  const toggleActive = async (s) => {
    try {
      await api.patch(`/bus-stops/${s.id}`, { active: !s.active });
      toast.success(s.active ? 'Stop set inactive' : 'Stop re-activated');
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); }
  };
  const remove = async (s) => {
    if (!window.confirm(`Delete stop #${s.stop_no} — ${s.stop_name}? Students assigned to this stop must be reassigned first.`)) return;
    try {
      await api.delete(`/bus-stops/${s.id}`);
      toast.success('Stop deleted');
      load();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); }
  };

  const filtered = stops.filter(s => {
    if (!q) return true;
    const needle = q.toLowerCase();
    return String(s.stop_no).includes(needle) || (s.stop_name || '').toLowerCase().includes(needle);
  });
  const activeCount = stops.filter(s => s.active !== false).length;
  const totalCollection = stops.reduce((sum, s) => sum + (s.active !== false ? Number(s.monthly_fee || 0) : 0), 0);

  return (
    <>
      <PageHeader
        title="Bus Stop Master"
        subtitle={`${stops.length} stops · ${activeCount} active · avg ₹${stops.length ? Math.round(totalCollection / activeCount) : 0}/student/month`}
        actions={canEdit && (
          <button data-testid="bs-new" onClick={() => setCreating(true)} className="h-9 px-3 bg-blue-600 text-white rounded text-sm flex items-center gap-1.5 hover:bg-blue-700">
            <Plus className="w-4 h-4" /> New Stop
          </button>
        )}
      />
      <div className="p-6 space-y-4">
        <div className="bg-white border border-slate-200 rounded p-3 flex items-center gap-3">
          <Search className="w-4 h-4 text-slate-400" />
          <input
            className="flex-1 h-8 text-sm outline-none"
            placeholder="Search stop number or name…"
            value={q} onChange={e => setQ(e.target.value)}
            data-testid="bs-search"
          />
          <span className="text-[11px] text-slate-500">{filtered.length} shown</span>
        </div>

        <div className="bg-white border border-slate-200 rounded overflow-hidden">
          <table className="w-full dense-table">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wide text-slate-600 bg-slate-50">
                <th className="pl-3 py-2 w-16">#</th>
                <th>Stop Name</th>
                <th className="text-right w-32">Monthly Fee</th>
                <th className="w-24">Status</th>
                {canEdit && <th className="w-40 text-right pr-3">Actions</th>}
              </tr>
            </thead>
            <tbody data-testid="bs-table">
              {filtered.length === 0 && (
                <tr><td colSpan={canEdit ? 5 : 4} className="text-center py-8 text-slate-500">No stops match — try clearing the search or add one from the button above.</td></tr>
              )}
              {filtered.map(s => (
                <tr key={s.id} className={s.active === false ? 'opacity-50' : ''} data-testid={`bs-row-${s.stop_no}`}>
                  <td className="pl-3 font-mono text-[13px]">{s.stop_no}</td>
                  <td className="font-medium">{s.stop_name}</td>
                  <td className="text-right tabular font-mono">{inr(s.monthly_fee)}</td>
                  <td>
                    <span className={`text-[10px] uppercase px-1.5 py-0.5 rounded ${s.active !== false ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'}`}>
                      {s.active !== false ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  {canEdit && (
                    <td className="text-right pr-3 space-x-1">
                      <button onClick={() => setEditing(s)} className="h-7 px-2 border border-slate-300 rounded text-[11px] hover:bg-slate-50 inline-flex items-center gap-1" data-testid={`bs-edit-${s.stop_no}`}>
                        <Pencil className="w-3 h-3" /> Edit
                      </button>
                      <button onClick={() => toggleActive(s)} className="h-7 px-2 border border-slate-300 rounded text-[11px] hover:bg-slate-50 inline-flex items-center gap-1" data-testid={`bs-toggle-${s.stop_no}`}>
                        {s.active !== false ? <><PowerOff className="w-3 h-3" /> Deactivate</> : <><Power className="w-3 h-3" /> Activate</>}
                      </button>
                      {canDelete && (
                        <button onClick={() => remove(s)} className="h-7 px-2 border border-red-300 text-red-700 rounded text-[11px] hover:bg-red-50 inline-flex items-center gap-1" data-testid={`bs-del-${s.stop_no}`}>
                          <Trash2 className="w-3 h-3" /> Delete
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {editing && <StopModal stop={editing} onClose={() => setEditing(null)} onDone={() => { setEditing(null); load(); }} />}
      {creating && <StopModal onClose={() => setCreating(false)} onDone={() => { setCreating(false); load(); }} />}
    </>
  );
}

function StopModal({ stop, onClose, onDone }) {
  const isEdit = !!stop;
  const [f, setF] = useState({
    stop_no: stop?.stop_no ?? '',
    stop_name: stop?.stop_name ?? '',
    monthly_fee: stop?.monthly_fee ?? '',
    academic_year: stop?.academic_year ?? '2026-27',
  });
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      if (isEdit) {
        await api.patch(`/bus-stops/${stop.id}`, {
          stop_name: f.stop_name,
          monthly_fee: parseFloat(f.monthly_fee) || 0,
          academic_year: f.academic_year,
        });
        toast.success('Bus stop updated');
      } else {
        await api.post('/bus-stops', {
          stop_no: parseInt(f.stop_no, 10),
          stop_name: f.stop_name,
          monthly_fee: parseFloat(f.monthly_fee) || 0,
          academic_year: f.academic_year,
        });
        toast.success('Bus stop added');
      }
      onDone();
    } catch (ex) { toast.error(ex?.response?.data?.detail || 'Failed'); }
    setBusy(false);
  };
  return (
    <div className="fixed inset-0 bg-slate-900/40 flex items-center justify-center z-50 p-4">
      <form onSubmit={submit} className="bg-white rounded shadow-lg w-full max-w-md" data-testid="bs-modal">
        <div className="px-5 py-3 border-b border-slate-200 font-heading font-medium flex items-center gap-2">
          <Bus className="w-4 h-4" />{isEdit ? `Edit Stop #${stop.stop_no}` : 'New Bus Stop'}
        </div>
        <div className="p-5 space-y-3">
          <label className="block">
            <div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">Stop Number *</div>
            <input required type="number" min="1" disabled={isEdit}
              className="w-full h-9 px-3 border border-slate-300 rounded text-sm bg-white disabled:bg-slate-100"
              value={f.stop_no} onChange={e => setF({ ...f, stop_no: e.target.value })}
              data-testid="bs-input-no"
            />
          </label>
          <label className="block">
            <div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">Stop Name *</div>
            <input required className="w-full h-9 px-3 border border-slate-300 rounded text-sm"
              value={f.stop_name} onChange={e => setF({ ...f, stop_name: e.target.value })}
              placeholder="Butibori - Railway Station"
              data-testid="bs-input-name"
            />
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label className="block">
              <div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">Monthly Fee (₹) *</div>
              <input required type="number" min="0" step="10"
                className="w-full h-9 px-3 border border-slate-300 rounded text-sm text-right font-mono"
                value={f.monthly_fee} onChange={e => setF({ ...f, monthly_fee: e.target.value })}
                data-testid="bs-input-fee"
              />
            </label>
            <label className="block">
              <div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">Academic Year</div>
              <input className="w-full h-9 px-3 border border-slate-300 rounded text-sm"
                value={f.academic_year} onChange={e => setF({ ...f, academic_year: e.target.value })}
              />
            </label>
          </div>
        </div>
        <div className="flex justify-end gap-2 px-5 py-3 border-t border-slate-200 bg-slate-50">
          <button type="button" onClick={onClose} className="h-9 px-3 border border-slate-300 rounded text-sm">Cancel</button>
          <button data-testid="bs-submit" disabled={busy} className="h-9 px-4 bg-blue-600 text-white rounded text-sm disabled:opacity-60">
            {busy ? 'Saving…' : isEdit ? 'Save Changes' : 'Add Stop'}
          </button>
        </div>
      </form>
    </div>
  );
}
