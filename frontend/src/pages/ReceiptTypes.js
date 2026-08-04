import React, { useEffect, useState } from 'react';
import { toast } from 'sonner';
import api from '@/lib/api';
import { PageHeader } from '@/components/Layout';
import AdminPinPrompt from '@/components/AdminPinPrompt';
import { Plus, Edit2, Trash2, Eye, EyeOff, Save, X, Shield } from 'lucide-react';

const CATEGORIES = [
  { v: 'school',  label: 'School' },
  { v: 'bus',     label: 'Bus' },
  { v: 'finance', label: 'Finance' },
  { v: 'misc',    label: 'Misc' },
];
const ICON_CHOICES = ['GraduationCap','BookOpen','Award','Bus','ClipboardList','Wallet','School'];
const FIELD_KEYS = ['admission_no','roll_no','parent_name','mobile','class','division','department','academic_year','session','fee_head','amount_in_words','payment_mode','transaction_id','cashier_name','authorized_by','remarks'];
const FIELD_LABELS = { admission_no:'Admission No', roll_no:'Roll No', parent_name:'Parent Name', mobile:'Mobile', class:'Class', division:'Division', department:'Department', academic_year:'Academic Year', session:'Session', fee_head:'Fee Head', amount_in_words:'Amount in Words', payment_mode:'Payment Mode', transaction_id:'Transaction ID', cashier_name:'Cashier Name', authorized_by:'Authorized By', remarks:'Remarks' };

const empty = {
  code:'', name:'', department_name:'', category:'school', description:'', icon:'GraduationCap',
  display_order:100, enabled:true, tabs:['school','installment','misc'],
  paper_size:'A4', orientation:'portrait', header_text:'', footer_text:'', watermark_text:'', watermark_enabled:false,
  barcode_enabled:false, qr_enabled:true, signature_area_enabled:true, computer_generated_note:'This is a computer-generated receipt.',
  starting_number:1, auto_reset_yearly:true,
  fields: FIELD_KEYS.reduce((a,k)=>({...a,[k]: ['roll_no','division','session','authorized_by'].includes(k) ? false : true}), {}),
};


export default function ReceiptTypes() {
  const [rows, setRows] = useState([]);
  const [editing, setEditing] = useState(null); // full row or 'new'
  const [prompt, setPrompt] = useState(null);

  const load = () => api.get('/receipt-types?include_disabled=true').then(r => setRows(r.data)).catch(()=>toast.error('Failed to load'));
  useEffect(() => { load(); }, []);

  const withPin = (title, message, fn, dual = false) => setPrompt({ mode: dual ? 'dual' : 'pin', title, message, onOk: async (headers) => { await fn(headers); load(); } });

  const doSave = async (body, headers) => {
    if (editing === 'new') {
      await api.post('/receipt-types', body, { headers });
      toast.success('Receipt type created');
    } else {
      await api.patch(`/receipt-types/${editing.id}`, body, { headers });
      toast.success('Receipt type updated');
    }
    setEditing(null);
  };

  const doDelete = async (row, headers) => {
    try { await api.delete(`/receipt-types/${row.id}`, { headers }); toast.success('Deleted'); }
    catch (e) {
      const d = e?.response?.data?.detail;
      if (typeof d === 'object' && d?.can_archive) {
        if (window.confirm(`${d.message}\n\nArchive instead?`)) {
          await api.post(`/receipt-types/${row.id}/archive`, null, { headers });
          toast.success('Archived — history preserved');
        }
      } else { toast.error(typeof d === 'string' ? d : 'Delete failed'); }
    }
  };

  const toggle = (row) => withPin('Enable / Disable Receipt Type', 'Toggle visibility for cashiers.',
    async (h) => { await api.patch(`/receipt-types/${row.id}`, { enabled: !row.enabled }, { headers: h }); toast.success(row.enabled ? 'Disabled' : 'Enabled'); });

  return (
    <>
      <PageHeader title="Receipt Type Management"
        subtitle="Add, edit, archive receipt types. All changes require the Administrator PIN."
        actions={
          <button data-testid="rtm-new" onClick={() => setEditing('new')} className="h-9 px-4 bg-slate-900 text-white rounded text-sm flex items-center gap-1.5"><Plus className="w-4 h-4" /> New Receipt Type</button>
        }
      />
      <div className="p-6">
        <div className="bg-amber-50 border border-amber-200 rounded p-3 text-[12px] text-amber-900 mb-4 flex items-center gap-2">
          <Shield className="w-4 h-4" /> Every add / edit / delete / disable requires your Administrator PIN. Set the PIN in <b>My Profile → Security</b> if you haven't yet.
        </div>
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200 text-[11px] uppercase tracking-wide text-slate-600">
              <tr className="text-left">
                <th className="px-3 py-2">Order</th><th className="px-3 py-2">Prefix</th><th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Department</th><th className="px-3 py-2">Category</th>
                <th className="px-3 py-2">Status</th><th className="px-3 py-2 text-right">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && <tr><td colSpan="7" className="p-6 text-center text-slate-500 text-[13px]">No receipt types</td></tr>}
              {rows.map((r, i) => (
                <tr key={r.id} data-testid={`rtm-row-${r.code}`} className={`border-b border-slate-100 last:border-0 ${r.archived ? 'bg-slate-50 text-slate-400' : ''}`}>
                  <td className="px-3 py-2 font-mono text-[11px]">{r.display_order}</td>
                  <td className="px-3 py-2"><span className="font-mono font-bold px-2 py-0.5 rounded bg-slate-900 text-white text-[11px]">{r.code}</span></td>
                  <td className="px-3 py-2 font-medium">{r.name}</td>
                  <td className="px-3 py-2 text-[12px] text-slate-600">{r.department_name || '—'}</td>
                  <td className="px-3 py-2 capitalize text-[12px]">{r.category}</td>
                  <td className="px-3 py-2">
                    {r.archived ? <span className="text-[11px] text-slate-500 bg-slate-100 border border-slate-200 rounded-full px-2 py-0.5">Archived</span>
                     : r.enabled ? <span className="text-[11px] text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-2 py-0.5">Active</span>
                     : <span className="text-[11px] text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5">Disabled</span>}
                  </td>
                  <td className="px-3 py-2 text-right space-x-1">
                    <button data-testid={`rtm-edit-${r.code}`} onClick={()=>setEditing(r)} className="p-1.5 border border-slate-300 rounded text-slate-700 hover:bg-slate-50" title="Edit"><Edit2 className="w-3.5 h-3.5" /></button>
                    <button onClick={()=>toggle(r)} className="p-1.5 border border-slate-300 rounded text-slate-700 hover:bg-slate-50" title={r.enabled ? 'Disable' : 'Enable'}>{r.enabled ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}</button>
                    <button data-testid={`rtm-del-${r.code}`} onClick={()=>withPin('Delete Receipt Type', `Delete "${r.name}"?`, (h) => doDelete(r, h))} className="p-1.5 border border-red-300 text-red-700 rounded hover:bg-red-50" title="Delete"><Trash2 className="w-3.5 h-3.5" /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {editing && <EditModal row={editing === 'new' ? empty : editing} isNew={editing === 'new'}
        onCancel={() => setEditing(null)}
        onSave={(body) => withPin(editing === 'new' ? 'Create Receipt Type' : 'Edit Receipt Type', 'This action modifies receipt configuration.', (h) => doSave(body, h))} />}
      <AdminPinPrompt prompt={prompt} onClose={()=>setPrompt(null)} />
    </>
  );
}

const EditModal = ({ row, isNew, onCancel, onSave }) => {
  const [f, setF] = useState({ ...empty, ...row, fields: { ...empty.fields, ...(row.fields || {}) } });
  const [tab, setTab] = useState('general');
  const set = (k, v) => setF(x => ({ ...x, [k]: v }));
  const setField = (k, v) => setF(x => ({ ...x, fields: { ...x.fields, [k]: v } }));
  const submit = (e) => {
    e.preventDefault();
    if (!f.code || !f.name) return;
    onSave({ ...f, code: f.code.toUpperCase(), display_order: Number(f.display_order) || 100, starting_number: Number(f.starting_number) || 1 });
  };
  const TABS = [['general','General'],['printing','Printing'],['numbering','Numbering'],['fields','Fields']];
  return (
    <div className="fixed inset-0 bg-slate-900/60 z-40 flex items-center justify-center p-4" onClick={onCancel}>
      <form onSubmit={submit} onClick={e=>e.stopPropagation()} className="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col">
        <div className="px-5 py-3 border-b border-slate-200 flex items-center justify-between">
          <div className="font-heading font-semibold">{isNew ? 'New Receipt Type' : `Edit — ${row.name}`}</div>
          <button type="button" onClick={onCancel} className="text-slate-400 hover:text-slate-700"><X className="w-4 h-4" /></button>
        </div>
        <div className="px-5 pt-3 border-b border-slate-200 flex gap-1">
          {TABS.map(([v,l]) => (
            <button key={v} type="button" onClick={()=>setTab(v)} data-testid={`rtm-tab-${v}`}
              className={`px-3 pb-2 -mb-px border-b-2 text-[13px] ${tab===v ? 'border-blue-600 text-blue-700 font-semibold' : 'border-transparent text-slate-500 hover:text-slate-800'}`}>{l}</button>
          ))}
        </div>
        <div className="p-5 overflow-y-auto flex-1">
          {tab==='general' && (
            <div className="grid grid-cols-2 gap-3 text-[13px]">
              <Field label="Prefix (e.g. EP, MP, JCACS)" required><input data-testid="rtm-code" value={f.code} onChange={e=>set('code', e.target.value.toUpperCase())} maxLength={8} className="w-full h-9 px-3 border border-slate-300 rounded font-mono text-sm uppercase" placeholder="EP" /></Field>
              <Field label="Category"><select value={f.category} onChange={e=>set('category', e.target.value)} className="w-full h-9 px-3 border border-slate-300 rounded bg-white">{CATEGORIES.map(c => <option key={c.v} value={c.v}>{c.label}</option>)}</select></Field>
              <Field label="Receipt Name" required span={2}><input data-testid="rtm-name" value={f.name} onChange={e=>set('name', e.target.value)} className="w-full h-9 px-3 border border-slate-300 rounded text-sm" /></Field>
              <Field label="Department Name (printed)" span={2}><input value={f.department_name || ''} onChange={e=>set('department_name', e.target.value)} className="w-full h-9 px-3 border border-slate-300 rounded text-sm" /></Field>
              <Field label="Description" span={2}><textarea value={f.description || ''} onChange={e=>set('description', e.target.value)} rows={2} className="w-full px-3 py-2 border border-slate-300 rounded text-sm" /></Field>
              <Field label="Icon"><select value={f.icon || 'GraduationCap'} onChange={e=>set('icon', e.target.value)} className="w-full h-9 px-3 border border-slate-300 rounded bg-white">{ICON_CHOICES.map(i => <option key={i}>{i}</option>)}</select></Field>
              <Field label="Display Order"><input type="number" value={f.display_order || 100} onChange={e=>set('display_order', e.target.value)} className="w-full h-9 px-3 border border-slate-300 rounded" /></Field>
              <Field label="Enabled" span={2}>
                <label className="inline-flex items-center gap-2"><input type="checkbox" checked={!!f.enabled} onChange={e=>set('enabled', e.target.checked)} /> Show this receipt type to cashiers</label>
              </Field>
            </div>
          )}
          {tab==='printing' && (
            <div className="grid grid-cols-2 gap-3 text-[13px]">
              <Field label="Paper Size"><select value={f.paper_size} onChange={e=>set('paper_size', e.target.value)} className="w-full h-9 px-3 border border-slate-300 rounded bg-white">{['A4','A5','Thermal80'].map(x=><option key={x}>{x}</option>)}</select></Field>
              <Field label="Orientation"><select value={f.orientation} onChange={e=>set('orientation', e.target.value)} className="w-full h-9 px-3 border border-slate-300 rounded bg-white">{['portrait','landscape'].map(x=><option key={x}>{x}</option>)}</select></Field>
              <Field label="Header Text" span={2}><input value={f.header_text || ''} onChange={e=>set('header_text', e.target.value)} className="w-full h-9 px-3 border border-slate-300 rounded" placeholder="Extra line printed above the school name" /></Field>
              <Field label="Footer Text" span={2}><input value={f.footer_text || ''} onChange={e=>set('footer_text', e.target.value)} className="w-full h-9 px-3 border border-slate-300 rounded" placeholder="Extra line printed at the bottom" /></Field>
              <Field label="Watermark Text"><input value={f.watermark_text || ''} onChange={e=>set('watermark_text', e.target.value)} className="w-full h-9 px-3 border border-slate-300 rounded" placeholder="e.g. ORIGINAL / DUPLICATE" /></Field>
              <Field label="Watermark Enabled">
                <label className="inline-flex items-center gap-2 h-9"><input type="checkbox" checked={!!f.watermark_enabled} onChange={e=>set('watermark_enabled', e.target.checked)} /> Show watermark on printed receipt</label>
              </Field>
              <Field label="QR Code"><label className="inline-flex items-center gap-2 h-9"><input type="checkbox" checked={!!f.qr_enabled} onChange={e=>set('qr_enabled', e.target.checked)} /> Print verification QR</label></Field>
              <Field label="Barcode"><label className="inline-flex items-center gap-2 h-9"><input type="checkbox" checked={!!f.barcode_enabled} onChange={e=>set('barcode_enabled', e.target.checked)} /> Print receipt-no barcode</label></Field>
              <Field label="Signature Area"><label className="inline-flex items-center gap-2 h-9"><input type="checkbox" checked={!!f.signature_area_enabled} onChange={e=>set('signature_area_enabled', e.target.checked)} /> Show signature block</label></Field>
              <Field label="Computer Generated Note" span={2}><input value={f.computer_generated_note || ''} onChange={e=>set('computer_generated_note', e.target.value)} className="w-full h-9 px-3 border border-slate-300 rounded" /></Field>
            </div>
          )}
          {tab==='numbering' && (
            <div className="grid grid-cols-2 gap-3 text-[13px]">
              <Field label="Starting Number"><input type="number" value={f.starting_number || 1} onChange={e=>set('starting_number', e.target.value)} className="w-full h-9 px-3 border border-slate-300 rounded font-mono" /></Field>
              <Field label="Current Number (read-only)"><input type="number" value={f.current_number ?? ''} readOnly className="w-full h-9 px-3 border border-slate-300 rounded font-mono bg-slate-50" placeholder="auto" /></Field>
              <Field label="Auto-Reset on new Academic Year" span={2}>
                <label className="inline-flex items-center gap-2 h-9"><input type="checkbox" checked={!!f.auto_reset_yearly} onChange={e=>set('auto_reset_yearly', e.target.checked)} /> Sequence resets to Starting Number every academic year</label>
              </Field>
              <div className="col-span-2 p-3 bg-amber-50 border border-amber-200 rounded text-[12px] text-amber-900"><b>Manual reset</b> of the current number is a very high-risk action — it will require Admin PIN + Password (dual authorisation) and is coming in Phase 3.</div>
            </div>
          )}
          {tab==='fields' && (
            <div>
              <div className="text-[12px] text-slate-600 mb-3">Toggle which fields appear on this receipt template. Turning a field off hides it on both the entry form and the printed page.</div>
              <div className="grid grid-cols-2 gap-2">
                {FIELD_KEYS.map(k => (
                  <label key={k} className={`flex items-center justify-between px-3 py-2 border rounded ${f.fields?.[k] ? 'bg-emerald-50 border-emerald-200' : 'bg-slate-50 border-slate-200'}`}>
                    <span className="text-[13px]">{FIELD_LABELS[k]}</span>
                    <input data-testid={`rtm-field-${k}`} type="checkbox" checked={!!f.fields?.[k]} onChange={e=>setField(k, e.target.checked)} />
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>
        <div className="px-5 py-3 border-t border-slate-200 flex justify-end gap-2">
          <button type="button" onClick={onCancel} className="h-9 px-4 border border-slate-300 rounded text-sm">Cancel</button>
          <button type="submit" data-testid="rtm-save" className="h-9 px-4 bg-slate-900 text-white rounded text-sm font-semibold flex items-center gap-1.5"><Save className="w-4 h-4" /> Save (requires PIN)</button>
        </div>
      </form>
    </div>
  );
};
const Field = ({ label, children, span = 1, required = false }) => (
  <label className={`block ${span === 2 ? 'col-span-2' : ''}`}>
    <div className="text-[11px] uppercase tracking-widest text-slate-600 mb-1">{label}{required && <span className="text-red-600 ml-0.5">*</span>}</div>
    {children}
  </label>
);
