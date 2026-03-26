import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { jwtDecode } from 'jwt-decode';

interface User {
  id: number;
  nome: string;
  email: string;
}

interface AuthState {
  token: string | null;
  user: User | null;
  setAuth: (token: string, user: User) => void;
  logout: () => void;
  isTokenValid: () => boolean;
  getUserId: () => number;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      user: null,
      setAuth: (token: string, user: User) => set({ token, user }),
      logout: () => set({ token: null, user: null }),
      isTokenValid: () => {
        const { token } = get();
        if (!token) return false;
        try {
          const decoded = jwtDecode(token);
          if (!decoded.exp) return true;
          return decoded.exp * 1000 > Date.now();
        } catch {
          return false;
        }
      },
      getUserId: () => get().user?.id ?? 1,
    }),
    {
      name: 'luminacast-auth-storage',
    }
  )
);
