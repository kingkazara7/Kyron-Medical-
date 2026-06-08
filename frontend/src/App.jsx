import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import Login from './pages/Login';
import Dashboard from './pages/Dashboard';
import Workspace from './pages/Workspace';
import PatientHistory from './pages/PatientHistory';
import AdminDashboard from './pages/AdminDashboard';

function PrivateRoute({ children, adminOnly = false }) {
  const { user } = useAuth();
  // Also check that the token still exists — the api.js interceptor may
  // clear it without triggering a React re-render (e.g. on manual refresh)
  const hasToken = !!localStorage.getItem('token');
  if (!user || !hasToken) return <Navigate to="/login" replace />;
  if (adminOnly && user.role !== 'admin') return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/patient/:patientId" element={<PrivateRoute><PatientHistory /></PrivateRoute>} />
          <Route path="/encounter/:id" element={<PrivateRoute><Workspace /></PrivateRoute>} />
          <Route path="/admin" element={<PrivateRoute adminOnly><AdminDashboard /></PrivateRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
