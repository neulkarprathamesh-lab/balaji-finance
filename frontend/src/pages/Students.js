import React, { useEffect, useState } from 'react';
import api from '@/lib/api';
import { PageHeader } from '@/components/Layout';
import { Search, Plus, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export default function Students() {
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState('');
  const [depts, setDepts] = useState([]);
  const [classes, setClasses] = useState([]);
  const [dept, setDept] = useState('');
  const [openNew, setOpenNew] = useState(false);
  const nav = useNavigate();

  const load = () => {
    const p = new URLSearchParams();
    if (q) p.set('q', q);
    if (dept) p.set('department_id', dept);
    api.get(`/students?${p.toString()}`).then(r => setRows(r.data));
  };

  useEffect(() => {
    api.get('/departments').then(r => setDepts(r.data));
    api.get('/classes').then(r => setClasses(r.data));
  }, []);
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [dept]);

  const className = (id) => classes.find(c => c.id === id)?.name || '-';
  const deptName = (id) => depts.find(d => d.id === id)?.name || '-';

  return (
    <>
      <PageHeader title="Students" subtitle={`${rows.length} shown`} actions={
        <button data-testid="students-new" onClick={() => setOpenNew(true)} className="h-9 px-3 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded flex items-center gap-1.5">
          <Plus className="w-4 h-4" /> Add Student
        </button>
      } />
      <div className="p-6 space-y-4">
        <div className="bg-white border border-slate-200 rounded p-4 flex gap-3 items-end">
          <div className="flex-1 relative">
            <Search className="w-4 h-4 absolute left-3 top-3 text-slate-400" />
            <input
              data-testid="students-search"
              value={q} onChange={(e)=>setQ(e.target.value)} onKeyDown={(e)=>e.key==='Enter'&&load()}
              placeholder="Search by admission no, name or mobile…"
              className="h-10 w-full pl-9 pr-3 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:border-blue-600 focus:outline-none"
            />
          </div>
          <select data-testid="students-dept" value={dept} onChange={(e)=>setDept(e.target.value)} className="h-10 px-3 border border-slate-300 rounded text-sm bg-white">
            <option value="">All Departments</option>
            {depts.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}
          </select>
          <button onClick={load} className="h-10 px-4 bg-slate-900 text-white text-sm rounded hover:bg-slate-800">Search</button>
        </div>

        <div className="bg-white border border-slate-200 rounded overflow-hidden">
          <table className="w-full dense-table" data-testid="students-table">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wide text-slate-600">
                <th>Admission No</th><th>Name</th><th>Department</th><th>Class</th><th>Guardian</th><th>Mobile</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && <tr><td colSpan="7" className="text-center py-8 text-slate-500">No students found</td></tr>}
              {rows.map(s => (
                <tr key={s.id} className="cursor-pointer" onClick={() => nav(`/students/${s.id}`)}>
                  <td className="font-mono text-[12px]">{s.admission_no}</td>
                  <td className="font-medium">{s.name}</td>
                  <td>{deptName(s.department_id)}</td>
                  <td>{className(s.class_id)}</td>
                  <td>{s.guardian_name || '-'}</td>
                  <td className="font-mono text-[12px]">{s.guardian_mobile || '-'}</td>
                  <td><span className="text-[11px] px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 uppercase">{s.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {openNew && <NewStudent depts={depts} classes={classes} onClose={() => { setOpenNew(false); load(); }} />}
    </>
  );
}

function NewStudent({ depts, classes, onClose }) {
  const [f, setF] = useState({ admission_no:'', name:'', department_id:'', class_id:'', guardian_name:'', guardian_mobile:'', address:'' });
  const [err, setErr] = useState('');
  const set = (k, v) => setF({ ...f, [k]: v });
  const submit = async (e) => {
    e.preventDefault(); setErr('');
    try { await api.post('/students', f); onClose(); }
    catch (ex) {
      const d = ex?.response?.data?.detail;
      setErr(typeof d === 'string' ? d : 'Failed to save');
    }
  };
  const availClasses = classes.filter(c => c.department_id === f.department_id);
  return (
    <div className="fixed inset-0 bg-slate-900/40 flex items-center justify-center z-50 p-4">
      <form onSubmit={submit} className="bg-white rounded shadow-lg w-full max-w-lg" data-testid="new-student-form">
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200">
          <h3 className="font-heading font-medium">New Student</h3>
          <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-700"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-5 grid grid-cols-2 gap-4">
          <Field label="Admission No *"><input required data-testid="ns-admno" className={inp} value={f.admission_no} onChange={e=>set('admission_no', e.target.value)} /></Field>
          <Field label="Full Name *"><input required data-testid="ns-name" className={inp} value={f.name} onChange={e=>set('name', e.target.value)} /></Field>
          <Field label="Department *"><select required data-testid="ns-dept" className={inp} value={f.department_id} onChange={e=>set('department_id', e.target.value)}><option value="">Select…</option>{depts.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select></Field>
          <Field label="Class *"><select required data-testid="ns-class" className={inp} value={f.class_id} onChange={e=>set('class_id', e.target.value)}><option value="">Select…</option>{availClasses.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</select></Field>
          <Field label="Guardian Name"><input className={inp} value={f.guardian_name} onChange={e=>set('guardian_name', e.target.value)} /></Field>
          <Field label="Guardian Mobile"><input className={inp} value={f.guardian_mobile} onChange={e=>set('guardian_mobile', e.target.value)} /></Field>
          <div className="col-span-2"><Field label="Address"><textarea rows="2" className={inp} value={f.address} onChange={e=>set('address', e.target.value)} /></Field></div>
        </div>
        {err && <div className="mx-5 mb-3 text-sm text-red-600 bg-red-50 border border-red-200 rounded p-2">{err}</div>}
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-slate-200 bg-slate-50">
          <button type="button" onClick={onClose} className="h-9 px-3 border border-slate-300 rounded text-sm hover:bg-white">Cancel</button>
          <button data-testid="ns-submit" className="h-9 px-4 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">Save</button>
        </div>
      </form>
    </div>
  );
}

const inp = "w-full h-9 px-3 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:border-blue-600 focus:outline-none bg-white";
const Field = ({ label, children }) => (
  <label className="block">
    <div className="text-[11px] tracking-wide uppercase text-slate-600 mb-1">{label}</div>
    {children}
  </label>
);
