import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

export default function PublicRoute() {
  const isTokenValid = useAuthStore((state) => state.isTokenValid);

  if (isTokenValid()) {
    return <Navigate to="/home" replace />;
  }

  return <Outlet />;
}