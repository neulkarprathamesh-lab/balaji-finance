import React, { useEffect, useState } from 'react';
import api from '@/lib/api';
import { PageHeader, inr } from '@/components/Layout';
import { toast } from 'sonner';
import { Plus, Bus, Pencil, Trash2, PowerOff, Power, Search, TrendingUp, TrendingDown, IndianRupee } from 'lucide-react';
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
  const canBulk = ['administrator', 'manager'].includes(user?.role);
  const [stops, setStops] = useState([]);
  const [q, setQ] = useState('');
  const [editing, setEditing] = useState(null); // full stop being edited (null = closed)
  const [creating, setCreating] = useState(false);
  const [bulk, setBulk] = useState(false);

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
          <div className="flex gap-2">
            {canBulk && (
              <button data-testid="bs-bulk" onClick={() => setBulk(true)} className="h-9 px-3 border border-slate-300 text-slate-800 rounded text-sm flex items-center gap-1.5 hover:bg-white">
                <TrendingUp className="w-4 h-4" /> Bulk Fare Update
              </button>
            )}
            <button data-testid="bs-new" onClick={() => setCreating(true)} className="h-9 px-3 bg-blue-600 text-white rounded text-sm flex items-center gap-1.5 hover:bg-blue-700">
              <Plus className="w-4 h-4" /> New Stop
            </button>
          </div>
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
      {bulk && <BulkFareModal stops={stops} onClose={() => setBulk(false)} onDone={() => { setBulk(false); load(); }} />}
    </>
  );
}

function BulkFareModal({ stops, onClose, onDone }) {
  const [op, setOp] = useState('increase_percent');
  const [value, setValue] = useState('10');
  const [roundTo, setRoundTo] = useState('10');
  const [effective, setEffective] = useState(new Date().toISOString().slice(0, 10));
  const [reason, setReason] = useState('');
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);

  const runPreview = async () => {
    setBusy(true);
    try {
      const { data } = await api.post('/bus-stops/bulk-update', {
        operation: op, value: parseFloat(value) || 0, round_to: parseInt(roundTo, 10) || 1,
        preview: true, effective_date: effective, reason,
      });
      setPreview(data);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Preview failed'); }
    setBusy(false);
  };
  const apply = async () => {
    if (!window.confirm(`Apply new fares to ${preview.rows.length} stops? This affects ${preview.total_students_affected} students and cannot be undone from this screen (roll back via a config snapshot).`)) return;
    setBusy(true);
    try {
      const { data } = await api.post('/bus-stops/bulk-update', {
        operation: op, value: parseFloat(value) || 0, round_to: parseInt(roundTo, 10) || 1,
        preview: false, effective_date: effective, reason,
      });
      toast.success(`${data.stops_changed} stops updated · new monthly total ₹${data.total_new}`);
      onDone();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); }
    setBusy(false);
  };
  const OpBtn = ({ v, label, Icon }) => (
    <button
      type="button" onClick={() => { setOp(v); setPreview(null); }}
      className={`h-9 px-3 rounded text-[12px] font-medium inline-flex items-center gap-1.5 border ${op === v ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-slate-700 border-slate-300 hover:bg-slate-50'}`}
      data-testid={`bulk-op-${v}`}
    >
      <Icon className="w-3.5 h-3.5" /> {label}
    </button>
  );

  return (
    <div className="fixed inset-0 z-50 bg-slate-900/50 backdrop-blur-sm flex items-center justify-center p-4 no-print" data-testid="bulk-modal">
      <div className="w-full max-w-3xl bg-white rounded-xl shadow-2xl overflow-hidden max-h-[92vh] flex flex-col">
        <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between bg-slate-50">
          <div className="font-heading font-semibold flex items-center gap-2"><TrendingUp className="w-4 h-4" /> Bulk Bus Fare Update</div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-xl leading-none">×</button>
        </div>
        <div className="p-5 space-y-4 overflow-y-auto">
          <div className="flex flex-wrap gap-2">
            <OpBtn v="increase_percent" label="Increase by %" Icon={TrendingUp} />
            <OpBtn v="decrease_percent" label="Decrease by %" Icon={TrendingDown} />
            <OpBtn v="increase_fixed" label="Increase by ₹" Icon={IndianRupee} />
            <OpBtn v="decrease_fixed" label="Decrease by ₹" Icon={IndianRupee} />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <label className="block">
              <div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">Value {op.endsWith('percent') ? '(%)' : '(₹)'}</div>
              <input type="number" min="0" step="0.5" value={value} onChange={e => { setValue(e.target.value); setPreview(null); }}
                className="w-full h-9 px-3 border border-slate-300 rounded text-sm text-right font-mono" data-testid="bulk-value" />
            </label>
            <label className="block">
              <div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">Round new fare to nearest ₹</div>
              <select value={roundTo} onChange={e => { setRoundTo(e.target.value); setPreview(null); }} className="w-full h-9 px-3 border border-slate-300 rounded text-sm bg-white">
                <option value="1">No rounding</option>
                <option value="10">₹10</option>
                <option value="50">₹50</option>
                <option value="100">₹100</option>
              </select>
            </label>
            <label className="block">
              <div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">Effective from</div>
              <input type="date" value={effective} onChange={e => setEffective(e.target.value)} className="w-full h-9 px-3 border border-slate-300 rounded text-sm" data-testid="bulk-effective" />
            </label>
          </div>
          <label className="block">
            <div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">Reason (recorded in audit log)</div>
            <input value={reason} onChange={e => setReason(e.target.value)}
              placeholder="Annual fare revision for 2026-27" className="w-full h-9 px-3 border border-slate-300 rounded text-sm" data-testid="bulk-reason" />
          </label>
          <button onClick={runPreview} disabled={busy} data-testid="bulk-preview" className="h-9 px-4 bg-slate-900 hover:bg-slate-800 text-white rounded text-sm inline-flex items-center gap-1.5 disabled:opacity-50">
            {busy ? 'Working…' : 'Preview Changes →'}
          </button>

          {preview && (
            <div className="border border-slate-200 rounded overflow-hidden" data-testid="bulk-preview-table">
              <div className="grid grid-cols-3 gap-3 p-3 bg-slate-50 border-b border-slate-200 text-sm">
                <div><div className="text-[10px] uppercase tracking-widest text-slate-500">Stops touched</div><div className="font-heading font-semibold text-lg">{preview.rows.length}</div></div>
                <div><div className="text-[10px] uppercase tracking-widest text-slate-500">Students affected</div><div className="font-heading font-semibold text-lg">{preview.total_students_affected}</div></div>
                <div><div className="text-[10px] uppercase tracking-widest text-slate-500">Monthly total</div><div className="font-heading font-semibold text-lg tabular">{inr(preview.total_current)} → {inr(preview.total_new)}</div></div>
              </div>
              <div className="max-h-64 overflow-y-auto">
                <table className="w-full dense-table text-[12px]">
                  <thead className="bg-white sticky top-0"><tr className="text-left text-[10px] uppercase tracking-widest text-slate-500 border-b border-slate-200"><th className="pl-3 py-1.5">#</th><th>Stop</th><th className="text-right">Current</th><th className="text-right">New</th><th className="text-right">Δ</th><th className="text-right pr-3">Students</th></tr></thead>
                  <tbody>
                    {preview.rows.map(r => (
                      <tr key={r.id} className="border-b border-slate-100">
                        <td className="pl-3 py-1 font-mono">{r.stop_no}</td>
                        <td>{r.stop_name}</td>
                        <td className="text-right font-mono">{inr(r.current_fare)}</td>
                        <td className="text-right font-mono font-semibold">{inr(r.new_fare)}</td>
                        <td className={`text-right font-mono ${r.delta > 0 ? 'text-emerald-700' : r.delta < 0 ? 'text-rose-700' : 'text-slate-400'}`}>{r.delta > 0 ? '+' : ''}{inr(r.delta)}</td>
                        <td className="text-right pr-3">{r.students_affected}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
        <div className="flex justify-end gap-2 px-5 py-3 border-t border-slate-200 bg-slate-50">
          <button onClick={onClose} className="h-9 px-3 border border-slate-300 rounded text-sm">Cancel</button>
          <button onClick={apply} disabled={!preview || busy}
            className="h-9 px-4 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-300 text-white rounded text-sm font-semibold"
            data-testid="bulk-apply">
            {busy ? 'Applying…' : preview ? 'Confirm & Apply' : 'Run preview first'}
          </button>
        </div>
      </div>
    </div>
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
