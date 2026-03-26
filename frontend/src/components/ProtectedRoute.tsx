import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

export default function ProtectedRoute() {
  const isTokenValid = useAuthStore((state) => state.isTokenValid);

  if (!isTokenValid()) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
