import React, { useEffect, useState } from 'react';
import api from '@/lib/api';
import { PageHeader, inr } from '@/components/Layout';
import { toast } from 'sonner';
import { Sparkles } from 'lucide-react';

export default function FeeStructure() {
  const [depts, setDepts] = useState([]);
  const [classes, setClasses] = useState([]);
  const [feeHeads, setFeeHeads] = useState([]);
  const [structures, setStructures] = useState([]);
  const [dept, setDept] = useState('');
  const [cls, setCls] = useState('');
  const [items, setItems] = useState([]);
  const [dup, setDup] = useState(null);
  const [seeding, setSeeding] = useState(false);

  const reload = async () => {
    const [d, c, h, s] = await Promise.all([
      api.get('/departments'), api.get('/classes'), api.get('/fee-heads'), api.get('/fee-structures')
    ]);
    setDepts(d.data); setClasses(c.data); setFeeHeads(h.data); setStructures(s.data);
  };
  useEffect(() => { reload(); }, []);

  const seed2026 = async () => {
    if (!window.confirm('Load all 29 fee structures from the 2026-27 PDF? Classes will be created for English / Semi-English / Junior College mediums. Existing structures are skipped.')) return;
    setSeeding(true);
    try {
      const { data } = await api.post('/fee-structures/seed-2026');
      toast.success(`✓ ${data.structures_created} structures created · ${data.classes_created} new classes · ${data.skipped} skipped (of ${data.total_rows} rows in PDF)`);
      await reload();
    } catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); }
    setSeeding(false);
  };

  useEffect(() => {
    api.get('/departments').then(r => setDepts(r.data));
    api.get('/classes').then(r => setClasses(r.data));
    api.get('/fee-heads').then(r => setFeeHeads(r.data));
    api.get('/fee-structures').then(r => setStructures(r.data));
  }, []);

  const availClasses = classes.filter(c => c.department_id === dept);
  const total = items.reduce((s,i)=>s+(parseFloat(i.amount)||0),0);

  const addItem = () => setItems([...items, { fee_head_id:'', amount:0 }]);
  const save = async () => {
    if (!dept || !cls) return toast.error('Select department & class');
    try {
      await api.post('/fee-structures', { department_id: dept, class_id: cls, academic_year:'2026-27', items });
      toast.success('Saved');
      await reload();
      setItems([]);
    } catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); }
  };

  return (
    <>
      <PageHeader title="Fee Structure" subtitle="Define per department + class + academic year"
        actions={
          <button data-testid="fs-seed" onClick={seed2026} disabled={seeding} className="h-9 px-3 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white text-sm rounded flex items-center gap-1.5">
            <Sparkles className="w-4 h-4" /> {seeding ? 'Loading…' : 'Load 2026-27 (29 classes)'}
          </button>
        }
      />
      <div className="p-6 grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded p-4">
          <div className="grid grid-cols-2 gap-4 mb-4">
            <F label="Department"><select className={inp} value={dept} onChange={e=>{setDept(e.target.value); setCls('');}}><option value="">Select…</option>{depts.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></F>
            <F label="Class"><select className={inp} value={cls} onChange={e=>setCls(e.target.value)}><option value="">Select…</option>{availClasses.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></F>
          </div>
          <div className="text-[11px] uppercase tracking-wide text-slate-600 mb-2">Line Items</div>
          <table className="w-full dense-table">
            <thead><tr className="text-left text-[11px] uppercase text-slate-600"><th>Fee Head</th><th className="text-right">Amount</th></tr></thead>
            <tbody>
              {items.map((it, i) => (
                <tr key={i}>
                  <td><select className={`${inp} h-8`} value={it.fee_head_id} onChange={e=>{const c=[...items]; c[i].fee_head_id=e.target.value; setItems(c);}}>
                    <option value="">--</option>{feeHeads.map(fh=><option key={fh.id} value={fh.id}>{fh.name}</option>)}
                  </select></td>
                  <td><input type="number" className={`${inp} h-8 text-right`} value={it.amount} onChange={e=>{const c=[...items]; c[i].amount=e.target.value; setItems(c);}} /></td>
                </tr>
              ))}
            </tbody>
            <tfoot><tr className="border-t border-slate-200 bg-slate-50"><td className="text-right font-medium">Total</td><td className="text-right font-mono tabular font-semibold">{inr(total)}</td></tr></tfoot>
          </table>
          <div className="flex justify-between mt-3">
            <button onClick={addItem} className="text-sm text-blue-700 hover:underline">+ Add item</button>
            <button onClick={save} data-testid="fs-save" className="h-9 px-4 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">Save Structure</button>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded">
          <div className="px-4 py-2 border-b border-slate-200 font-heading font-medium text-sm">Existing Structures</div>
          <div className="max-h-[500px] overflow-y-auto">
            {structures.length===0 && <div className="p-4 text-sm text-slate-500">None yet</div>}
            {structures.map(s => {
              const d = depts.find(x=>x.id===s.department_id);
              const c = classes.find(x=>x.id===s.class_id);
              return <div key={s.id} className="p-3 border-b border-slate-100 text-sm flex items-center justify-between gap-2">
                <div>
                  <div className="font-medium">{d?.name} · {c?.name}</div>
                  <div className="text-xs text-slate-500">{s.academic_year} · <span className="font-mono tabular font-medium text-slate-900">{inr(s.total)}</span></div>
                </div>
                <button
                  data-testid={`fs-dup-${s.id}`}
                  onClick={() => setDup(s)}
                  className="text-xs h-7 px-2 border border-slate-300 rounded hover:bg-slate-50 text-slate-700"
                >Duplicate →</button>
              </div>;
            })}
          </div>
        </div>
      </div>
      {dup && <DuplicateModal src={dup} classes={classes} depts={depts} onClose={() => setDup(null)} onDone={async () => { setDup(null); const { data } = await api.get('/fee-structures'); setStructures(data); }} />}
    </>
  );
}

function DuplicateModal({ src, classes, depts, onClose, onDone }) {
  const [toClass, setToClass] = useState('');
  const [toAy, setToAy] = useState(src.academic_year || '');
  const [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    if (!toClass) return toast.error('Select target class');
    setBusy(true);
    try { await api.post(`/fee-structures/${src.id}/duplicate`, { to_class_id: toClass, to_academic_year: toAy }); toast.success('Fee structure duplicated'); onDone(); }
    catch (ex) { toast.error(ex?.response?.data?.detail || 'Failed'); }
    setBusy(false);
  };
  const srcClass = classes.find(c => c.id === src.class_id);
  const srcDept = depts.find(d => d.id === src.department_id);
  return (
    <div className="fixed inset-0 bg-slate-900/40 flex items-center justify-center z-50 p-4">
      <form onSubmit={submit} className="bg-white rounded shadow-lg w-full max-w-md" data-testid="fs-dup-modal">
        <div className="px-5 py-3 border-b border-slate-200 font-heading font-medium">Duplicate Fee Structure</div>
        <div className="p-5 space-y-3">
          <div className="bg-slate-50 border border-slate-200 rounded p-3 text-sm">
            <div className="text-[11px] uppercase tracking-widest text-slate-500 mb-1">Source</div>
            <div>{srcDept?.name} · {srcClass?.name}</div>
            <div className="text-[12px] text-slate-500">{src.academic_year} · Total <span className="font-mono tabular font-medium">{inr(src.total)}</span> · {src.items?.length} items</div>
          </div>
          <label className="block"><div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">Target Class *</div>
            <select required className="w-full h-9 px-3 border border-slate-300 rounded text-sm bg-white" value={toClass} onChange={e=>setToClass(e.target.value)}>
              <option value="">Select…</option>
              {classes.filter(c => c.id !== src.class_id).map(c => {
                const d = depts.find(x => x.id === c.department_id);
                return <option key={c.id} value={c.id}>{d?.name} · {c.name}</option>;
              })}
            </select>
          </label>
          <label className="block"><div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">Target Academic Year</div>
            <input className="w-full h-9 px-3 border border-slate-300 rounded text-sm bg-white" value={toAy} onChange={e=>setToAy(e.target.value)} placeholder="2026-27" />
          </label>
        </div>
        <div className="flex justify-end gap-2 px-5 py-3 border-t border-slate-200 bg-slate-50">
          <button type="button" onClick={onClose} className="h-9 px-3 border border-slate-300 rounded text-sm">Cancel</button>
          <button data-testid="fs-dup-submit" disabled={busy} className="h-9 px-4 bg-blue-600 text-white rounded text-sm disabled:opacity-60">{busy ? 'Duplicating…' : 'Duplicate'}</button>
        </div>
      </form>
    </div>
  );
}
const inp = "w-full h-9 px-3 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:border-blue-600 focus:outline-none bg-white";
const F = ({label,children}) => <label className="block"><div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">{label}</div>{children}</label>;
