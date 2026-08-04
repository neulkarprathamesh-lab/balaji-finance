import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import { Toaster } from 'sonner';
import Layout from '@/components/Layout';
import Login from '@/pages/Login';
import Dashboard from '@/pages/Dashboard';
import Students from '@/pages/Students';
import StudentDetail from '@/pages/StudentDetail';
import NewReceipt from '@/pages/NewReceipt';
import Receipts from '@/pages/Receipts';
import ReceiptView from '@/pages/ReceiptView';
import Adjustments from '@/pages/Adjustments';
import Extensions from '@/pages/Extensions';
import Reminders from '@/pages/Reminders';
import Reports from '@/pages/Reports';
import FeeStructure from '@/pages/FeeStructure';
import Admin from '@/pages/Admin';
import Cancellations from '@/pages/Cancellations';
import Concessions from '@/pages/Concessions';
import '@/index.css';

const Protected = ({ children, roles }) => {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-sm text-slate-500">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
};

export default function App() {
  return (
    <AuthProvider>
      <Toaster position="top-right" richColors />
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Protected><Layout /></Protected>}>
            <Route index element={<Dashboard />} />
            <Route path="students" element={<Students />} />
            <Route path="students/:id" element={<StudentDetail />} />
            <Route path="new-receipt" element={<NewReceipt />} />
            <Route path="receipts" element={<Receipts />} />
            <Route path="adjustments" element={<Adjustments />} />
            <Route path="extensions" element={<Extensions />} />
            <Route path="reminders" element={<Reminders />} />
            <Route path="reports" element={<Reports />} />
            <Route path="cancellations" element={<Protected roles={['administrator','manager','accountant']}><Cancellations /></Protected>} />
            <Route path="concessions" element={<Protected roles={['administrator','manager','accountant']}><Concessions /></Protected>} />
            <Route path="fee-structure" element={<Protected roles={['administrator','manager','accountant']}><FeeStructure /></Protected>} />
            <Route path="admin" element={<Protected roles={['administrator']}><Admin /></Protected>} />
          </Route>
          <Route path="/receipts/:id" element={<Protected><ReceiptView /></Protected>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
