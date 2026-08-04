import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '@/context/AuthContext';
import {
  LayoutDashboard, Users, Receipt, FileEdit, CalendarClock, Bell,
  FileText, BarChart3, LogOut, Wallet, Shield, XCircle, Award, Bus, GraduationCap, Mail, Settings2, User as UserIcon, Lock as LockIcon, ClipboardList, BookOpen
} from 'lucide-react';

const nav = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, roles: ['*'] },
  { to: '/students', label: 'Students', icon: Users, roles: ['*'] },
  { to: '/new-receipt', label: 'New Receipt', icon: Receipt, roles: ['*'] },
  { to: '/receipts', label: 'Receipts', icon: FileText, roles: ['*'] },
  { to: '/adjustments', label: 'Fee Adjustments', icon: FileEdit, roles: ['*'] },
  { to: '/extensions', label: 'Payment Extensions', icon: CalendarClock, roles: ['*'] },
  { to: '/reminders', label: 'Reminders', icon: Bell, roles: ['*'] },
  { to: '/bus-routes', label: 'Bus Routes', icon: Bus, roles: ['*'] },
  { to: '/fee-notices', label: 'Fee Notices', icon: Mail, roles: ['*'] },
  { to: '/reports', label: 'Reports', icon: BarChart3, roles: ['*'] },
  { to: '/cancellations', label: 'Cancellations', icon: XCircle, roles: ['administrator','manager','accountant'] },
  { to: '/concessions', label: 'Concession Ledger', icon: Award, roles: ['administrator','manager','accountant'] },
  { to: '/promotion', label: 'Promotion & Rollover', icon: GraduationCap, roles: ['administrator','manager'] },
  { to: '/assign-students', label: 'Assign Students', icon: ClipboardList, roles: ['administrator','manager','accountant'] },
  { to: '/fee-structure', label: 'Fee Structure', icon: Wallet, roles: ['administrator','manager','accountant'] },
  { to: '/fee-brochure', label: 'Fee Brochure', icon: BookOpen, roles: ['*'] },
  { to: '/settings', label: 'Settings', icon: Settings2, roles: ['administrator'] },
  { to: '/admin', label: 'Administration', icon: Shield, roles: ['administrator'] },
];

const roleColors = {
  administrator: 'bg-slate-900 text-white',
  manager: 'bg-blue-700 text-white',
  accountant: 'bg-emerald-700 text-white',
  cashier: 'bg-amber-700 text-white',
};

export default function Layout() {
  const { user, logout, lock } = useAuth();
  const navigate = useNavigate();

  const visible = nav.filter(n => n.roles.includes('*') || n.roles.includes(user?.role));

  return (
    <div className="min-h-screen flex bg-slate-50">
      <aside className="w-60 bg-slate-900 text-slate-100 flex flex-col no-print">
        <div className="px-5 py-5 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <img src="https://customer-assets-0z36b82j.emergentagent.net/job_finance-hub-school/artifacts/ce0kfh6k_schoolo%20logo.jpeg" alt="Balaji Convent" className="w-10 h-10 rounded-full object-cover ring-1 ring-slate-700" />
            <div>
              <div className="font-heading font-semibold text-[15px] leading-tight">Balaji Convent</div>
              <div className="text-[11px] text-slate-400 tracking-wide">FEE MANAGEMENT</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 py-3 px-2 overflow-y-auto">
          {visible.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              data-testid={`nav-${item.to.replace(/\//g,'') || 'home'}`}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-3 py-2 rounded text-[13px] mb-0.5 transition-colors duration-150 ${
                  isActive ? 'bg-blue-600 text-white' : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`
              }
            >
              <item.icon className="w-4 h-4" strokeWidth={1.75} />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-slate-800 p-3">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center text-xs font-semibold">
              {user?.name?.[0]?.toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[13px] font-medium truncate">{user?.name}</div>
              <span className={`inline-block text-[10px] tracking-wide uppercase px-1.5 py-0.5 rounded ${roleColors[user?.role] || 'bg-slate-700'}`}>
                {user?.role}
              </span>
            </div>
          </div>
          <button
            data-testid="profile-btn"
            onClick={() => navigate('/profile')}
            className="w-full flex items-center gap-2 px-2 py-1.5 text-[13px] text-slate-300 hover:text-white hover:bg-slate-800 rounded mb-0.5"
          >
            <UserIcon className="w-4 h-4" /> My Profile
          </button>
          <button
            data-testid="lock-btn"
            onClick={lock}
            className="w-full flex items-center gap-2 px-2 py-1.5 text-[13px] text-slate-300 hover:text-white hover:bg-slate-800 rounded mb-0.5"
          >
            <LockIcon className="w-4 h-4" /> Lock Screen
          </button>
          <button
            data-testid="logout-btn"
            onClick={async () => { await logout(); navigate('/login'); }}
            className="w-full flex items-center gap-2 px-2 py-1.5 text-[13px] text-slate-300 hover:text-white hover:bg-slate-800 rounded"
          >
            <LogOut className="w-4 h-4" /> Logout
          </button>
        </div>
      </aside>
      <main className="flex-1 min-w-0 flex flex-col">
        <Outlet />
      </main>
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between no-print">
      <div>
        <h1 className="font-heading text-xl font-semibold tracking-tight text-slate-900">{title}</h1>
        {subtitle && <div className="text-[13px] text-slate-500 mt-0.5">{subtitle}</div>}
      </div>
      <div className="flex items-center gap-2">{actions}</div>
    </div>
  );
}

export const inr = (n) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(n || 0);
