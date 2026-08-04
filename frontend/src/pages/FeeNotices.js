import React, { useEffect, useState } from 'react';
import api from '@/lib/api';
import { PageHeader, inr } from '@/components/Layout';
import { Printer, FileText } from 'lucide-react';

export default function FeeNotices() {
  const [depts, setDepts] = useState([]);
  const [classes, setClasses] = useState([]);
  const [dept, setDept] = useState('');
  const [cls, setCls] = useState('');
  const [minAmount, setMinAmount] = useState(1);
  const [data, setData] = useState(null);
  const [selected, setSelected] = useState({});

  useEffect(() => {
    api.get('/departments').then(r => setDepts(r.data));
    api.get('/classes').then(r => setClasses(r.data));
  }, []);

  const availClasses = classes.filter(c => c.department_id === dept);
  const run = async () => {
    const p = new URLSearchParams();
    if (dept) p.set('department_id', dept);
    if (cls) p.set('class_id', cls);
    p.set('min_amount', minAmount);
    const { data } = await api.get(`/notices/outstanding?${p.toString()}`);
    setData(data);
    setSelected(Object.fromEntries(data.students.map(s => [s.student_id, true])));
  };
  const toggle = (id) => setSelected({...selected, [id]: !selected[id]});
  const toggleAll = () => {
    const all = data.students.every(s => selected[s.student_id]);
    setSelected(Object.fromEntries(data.students.map(s => [s.student_id, !all])));
  };
  const selectedCount = data?.students.filter(s => selected[s.student_id]).length || 0;

  return (
    <>
      <PageHeader title="Term Fee Notices" subtitle="Auto-generate printable outstanding-fee notices for parents (PTM handouts)"
        actions={data && data.students.length > 0 && (
          <button data-testid="fn-print" onClick={()=>window.print()} className="h-9 px-3 bg-blue-600 text-white text-sm rounded flex items-center gap-1.5 hover:bg-blue-700 no-print">
            <Printer className="w-4 h-4" /> Print {selectedCount} Notice{selectedCount===1?'':'s'}
          </button>
        )}
      />
      <div className="p-6 space-y-4">
        <div className="bg-white border border-slate-200 rounded p-4 flex flex-wrap gap-3 items-end no-print">
          <div><div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">Department</div>
            <select value={dept} onChange={e=>{setDept(e.target.value); setCls('');}} className="h-9 px-3 border border-slate-300 rounded text-sm bg-white"><option value="">All</option>{depts.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select>
          </div>
          <div><div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">Class</div>
            <select value={cls} onChange={e=>setCls(e.target.value)} className="h-9 px-3 border border-slate-300 rounded text-sm bg-white"><option value="">All</option>{availClasses.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select>
          </div>
          <div><div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">Min Outstanding (₹)</div>
            <input type="number" value={minAmount} onChange={e=>setMinAmount(e.target.value)} className="h-9 w-28 px-3 border border-slate-300 rounded text-sm" />
          </div>
          <button data-testid="fn-run" onClick={run} className="h-9 px-4 bg-slate-900 text-white rounded text-sm">Generate</button>
        </div>

        {data && (
          <>
            <div className="bg-white border border-slate-200 rounded no-print">
              <div className="px-4 py-2 border-b border-slate-200 flex items-center justify-between">
                <div className="text-sm text-slate-700"><b>{data.count}</b> students have outstanding fees · <b>{selectedCount}</b> selected to print</div>
                <button onClick={toggleAll} className="text-xs text-blue-700 hover:underline">Toggle all</button>
              </div>
              <table className="w-full dense-table">
                <thead><tr className="text-left text-[11px] uppercase tracking-wide text-slate-600"><th className="w-8"></th><th>Adm No</th><th>Student</th><th>Class</th><th>Guardian</th><th className="text-right">Total Fee</th><th className="text-right">Paid</th><th className="text-right">Outstanding</th></tr></thead>
                <tbody>
                  {data.students.length === 0 && <tr><td colSpan="8" className="text-center py-6 text-slate-500">No students with outstanding fees</td></tr>}
                  {data.students.map(s => (
                    <tr key={s.student_id}>
                      <td><input type="checkbox" checked={!!selected[s.student_id]} onChange={()=>toggle(s.student_id)} /></td>
                      <td className="font-mono text-[12px]">{s.admission_no}</td>
                      <td className="font-medium">{s.name}</td>
                      <td className="text-[12px]">{s.class_name}</td>
                      <td className="text-[12px]">{s.guardian_name || '-'} <span className="text-slate-500 font-mono">{s.guardian_mobile}</span></td>
                      <td className="text-right tabular text-[12px]">{inr(s.total_fee)}</td>
                      <td className="text-right tabular text-[12px] text-emerald-700">{inr(s.paid)}</td>
                      <td className="text-right tabular font-semibold text-red-700">{inr(s.outstanding)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Printable notice sheets */}
            <div className="hidden print:block space-y-0" data-testid="fn-print-area">
              {data.students.filter(s => selected[s.student_id]).map(s => <Notice key={s.student_id} s={s} />)}
            </div>

            {/* Preview */}
            {selectedCount > 0 && (
              <div className="space-y-4">
                <div className="text-[11px] uppercase tracking-widest text-slate-500 font-medium no-print">Preview (first notice)</div>
                <Notice s={data.students.find(x => selected[x.student_id])} preview />
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}

function Notice({ s, preview = false }) {
  return (
    <div className={`bg-white border border-slate-300 mx-auto ${preview ? 'max-w-2xl' : ''}`} style={{ pageBreakAfter: 'always', minHeight: preview ? undefined : '95vh' }}>
      <div className="p-6">
        <div className="flex items-center gap-4 border-b-2 border-slate-900 pb-3 mb-4">
          <img src="https://customer-assets-0z36b82j.emergentagent.net/job_finance-hub-school/artifacts/ce0kfh6k_schoolo%20logo.jpeg" alt="logo" className="w-16 h-16 rounded-full object-cover" />
          <div>
            <div className="font-heading text-xl font-bold tracking-tight">BALAJI CONVENT & JUNIOR COLLEGE</div>
            <div className="text-[12px] text-slate-700">Butibori, Nagpur · {s.department_name} · Academic Year {s.academic_year || '—'}</div>
          </div>
        </div>
        <div className="text-center text-[13px] uppercase tracking-widest font-semibold my-3">Outstanding Fee Notice</div>
        <div className="text-sm mb-4">
          Date: <span className="font-mono">{new Date().toLocaleDateString('en-IN')}</span>
        </div>
        <div className="grid grid-cols-2 gap-2 text-sm mb-4 border border-slate-300 p-3 rounded">
          <div><span className="text-slate-500">Student: </span><b>{s.name}</b></div>
          <div><span className="text-slate-500">Admission No: </span><span className="font-mono">{s.admission_no}</span></div>
          <div><span className="text-slate-500">Class: </span>{s.class_name}</div>
          <div><span className="text-slate-500">Guardian: </span>{s.guardian_name || '—'}</div>
          <div className="col-span-2"><span className="text-slate-500">Contact: </span>{s.guardian_mobile || '—'}</div>
        </div>

        <p className="text-sm text-slate-800 mb-3">Dear Parent / Guardian, our records show the following pending fee for your ward. Kindly clear it at the school fee counter at the earliest.</p>

        <table className="w-full text-sm border-t border-b border-slate-400 my-3">
          <thead><tr className="border-b border-slate-400"><th className="text-left py-1.5">Particulars</th><th className="text-right">Amount</th></tr></thead>
          <tbody>
            <tr><td className="py-1">Total Annual Fee</td><td className="text-right tabular">{inr(s.total_fee)}</td></tr>
            <tr><td className="py-1">Less: Amount Paid</td><td className="text-right tabular text-emerald-700">− {inr(s.paid)}</td></tr>
            {s.adjusted > 0 && <tr><td className="py-1">Less: Concession / Adjustment</td><td className="text-right tabular text-emerald-700">− {inr(s.adjusted)}</td></tr>}
            {s.refunded > 0 && <tr><td className="py-1">Add: Refunded</td><td className="text-right tabular">+ {inr(s.refunded)}</td></tr>}
          </tbody>
          <tfoot>
            <tr className="border-t-2 border-slate-900"><td className="py-2 font-semibold">Amount Outstanding</td><td className="text-right tabular font-bold text-red-700 text-lg">{inr(s.outstanding)}</td></tr>
          </tfoot>
        </table>

        <div className="text-[12px] text-slate-600 mt-3">Fee counter timing: 9:00 AM – 3:00 PM (Monday to Saturday). Modes accepted: Cash / Cheque / DD / UPI / NEFT.</div>

        <div className="mt-8 pt-4 border-t border-dashed border-slate-400">
          <div className="text-[11px] text-slate-500 uppercase tracking-widest text-center mb-3">— Acknowledgement / Return Slip —</div>
          <div className="grid grid-cols-2 gap-4 text-[12px]">
            <div>Student: <b>{s.name}</b> ({s.admission_no})</div>
            <div>Class: {s.class_name}</div>
            <div>Outstanding: <b className="text-red-700 tabular">{inr(s.outstanding)}</b></div>
            <div>Received on: _______________</div>
          </div>
          <div className="grid grid-cols-2 gap-8 mt-8 text-[11px] text-slate-600">
            <div className="border-t border-slate-400 pt-1 text-center">Parent / Guardian Signature</div>
            <div className="border-t border-slate-400 pt-1 text-center">Class Teacher</div>
          </div>
        </div>
      </div>
    </div>
  );
}
