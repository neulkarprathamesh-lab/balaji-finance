import React, { useEffect, useState } from 'react';
import api from '@/lib/api';
import { PageHeader } from '@/components/Layout';
import { toast } from 'sonner';

export default function Admin() {
  const [users, setUsers] = useState([]);
  const [audit, setAudit] = useState([]);
  const [tab, setTab] = useState('users');
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ email:'', password:'', name:'', role:'cashier' });

  const load = () => {
    api.get('/users').then(r => setUsers(r.data));
    api.get('/reports/audit?limit=200').then(r => setAudit(r.data));
  };
  useEffect(load, []);

  const submit = async (e) => {
    e.preventDefault();
    try { await api.post('/users', f); toast.success('User created'); setOpen(false); setF({email:'',password:'',name:'',role:'cashier'}); load(); }
    catch (ex) { toast.error(ex?.response?.data?.detail || 'Failed'); }
  };

  return (
    <>
      <PageHeader title="Administration" subtitle="Users · audit log · settings" />
      <div className="p-6 space-y-4">
        <div className="flex gap-2 border-b border-slate-200">
          {[['users','Users'],['audit','Audit Log']].map(([k,l]) => (
            <button key={k} onClick={()=>setTab(k)} className={`px-4 py-2 text-sm border-b-2 ${tab===k?'border-blue-600 text-blue-700 font-medium':'border-transparent text-slate-600'}`}>{l}</button>
          ))}
        </div>

        {tab==='users' && <>
          <div className="flex justify-end"><button data-testid="admin-new-user" onClick={()=>setOpen(true)} className="h-9 px-3 bg-blue-600 text-white rounded text-sm hover:bg-blue-700">New User</button></div>
          <div className="bg-white border border-slate-200 rounded overflow-hidden">
            <table className="w-full dense-table">
              <thead><tr className="text-left text-[11px] uppercase tracking-wide text-slate-600"><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Created</th><th></th></tr></thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id}><td className="font-medium">{u.name}</td><td className="font-mono text-[12px]">{u.email}</td>
                    <td><span className="text-[11px] uppercase px-1.5 py-0.5 rounded bg-slate-200">{u.role}</span></td>
                    <td>{u.active !== false ? <span className="text-[11px] text-emerald-700">active</span> : <span className="text-[11px] text-red-700">disabled</span>}</td>
                    <td className="text-[12px] text-slate-500">{new Date(u.created_at).toLocaleDateString('en-IN')}</td>
                    <td>
                      {u.email !== 'neulkarprathamesh@gmail.com' && (
                        <button
                          data-testid={`user-toggle-${u.id}`}
                          onClick={async () => {
                            const willDisable = u.active !== false;
                            if (!window.confirm(`${willDisable ? 'Suspend' : 'Reactivate'} ${u.name}? Their audit history stays intact.`)) return;
                            try { await api.patch(`/users/${u.id}`, { active: !willDisable }); toast.success(willDisable ? 'User suspended' : 'User reactivated'); load(); }
                            catch (e) { toast.error(e?.response?.data?.detail || 'Failed'); }
                          }}
                          className={`text-xs px-2 py-0.5 rounded ${u.active !== false ? 'border border-red-300 text-red-700 hover:bg-red-50' : 'border border-emerald-300 text-emerald-700 hover:bg-emerald-50'}`}
                        >{u.active !== false ? 'Suspend' : 'Reactivate'}</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>}

        {tab==='audit' && (
          <div className="bg-white border border-slate-200 rounded overflow-hidden">
            <table className="w-full dense-table">
              <thead><tr className="text-left text-[11px] uppercase tracking-wide text-slate-600"><th>Timestamp</th><th>User</th><th>Role</th><th>Action</th><th>Entity</th><th>Details</th></tr></thead>
              <tbody>
                {audit.map(a => (
                  <tr key={a.id}>
                    <td className="text-[12px] font-mono">{new Date(a.timestamp).toLocaleString('en-IN')}</td>
                    <td className="text-[12px]">{a.user_email}</td>
                    <td className="text-[11px] uppercase">{a.user_role}</td>
                    <td className="text-[12px] font-medium capitalize">{a.action}</td>
                    <td className="text-[12px] capitalize">{a.entity}</td>
                    <td className="text-[11px] text-slate-500 font-mono max-w-md truncate">{JSON.stringify(a.details)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {open && (
        <div className="fixed inset-0 bg-slate-900/40 flex items-center justify-center z-50 p-4">
          <form onSubmit={submit} className="bg-white rounded shadow-lg w-full max-w-md">
            <div className="px-5 py-3 border-b border-slate-200 font-heading font-medium">New Staff User</div>
            <div className="p-5 space-y-3">
              <F label="Full Name"><input required className={inp} value={f.name} onChange={e=>setF({...f,name:e.target.value})} /></F>
              <F label="Email"><input required type="email" className={inp} value={f.email} onChange={e=>setF({...f,email:e.target.value})} /></F>
              <F label="Password"><input required type="text" className={inp} value={f.password} onChange={e=>setF({...f,password:e.target.value})} /></F>
              <F label="Role"><select className={inp} value={f.role} onChange={e=>setF({...f,role:e.target.value})}>{['cashier','accountant','manager','administrator'].map(r=><option key={r}>{r}</option>)}</select></F>
            </div>
            <div className="flex justify-end gap-2 px-5 py-3 border-t border-slate-200 bg-slate-50">
              <button type="button" onClick={()=>setOpen(false)} className="h-9 px-3 border border-slate-300 rounded text-sm">Cancel</button>
              <button className="h-9 px-4 bg-blue-600 text-white rounded text-sm">Create</button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
const inp = "w-full h-9 px-3 border border-slate-300 rounded text-sm focus:ring-2 focus:ring-blue-600 focus:border-blue-600 focus:outline-none bg-white";
const F = ({label,children}) => <label className="block"><div className="text-[11px] uppercase tracking-wide text-slate-600 mb-1">{label}</div>{children}</label>;
