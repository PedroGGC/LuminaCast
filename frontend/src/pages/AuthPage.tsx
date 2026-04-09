import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { supabase } from '../lib/supabase';
import { useAuthStore } from '../store/authStore';
import './AuthPage.css';

export default function AuthPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const setAuth = useAuthStore((state) => state.setAuth);

  const isRegisterRoute = location.pathname === '/register';
  const [isActive, setIsActive] = useState(isRegisterRoute);

  // Estados do formulário
  const [loginIdentifier, setLoginIdentifier] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [registerName, setRegisterName] = useState('');
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsActive(location.pathname === '/register');
    setError(null);
  }, [location.pathname]);

  const handleToggle = (registering: boolean) => {
    navigate(registering ? '/register' : '/login');
  };

  const handleGoogleLogin = async () => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: `${window.location.origin}/auth/oauth/google/callback`,
      }
    })
    
    if (error) {
      setError('Erro ao fazer login com Google')
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const formData = new URLSearchParams();
      formData.append('username', loginIdentifier);
      formData.append('password', loginPassword);

      const res = await api.post('/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });
      const { access_token } = res.data;
      
      // Busca as informações reais do usuário
      const userRes = await api.get('/auth/me', {
        headers: { Authorization: `Bearer ${access_token}` }
      });
      
      setAuth(access_token, userRes.data);
      navigate('/home');
    } catch (err: any) {
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (Array.isArray(detail)) {
          setError(detail.map((e: any) => e.msg).join(', '));
        } else {
          setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
        }
      } else {
        setError('Ocorreu um erro no login. Verifique suas credenciais.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.post('/auth/register', {
        nome: registerName,
        email: registerEmail,
        senha: registerPassword,
      });
      
      // Auto-login after successful registration
      const formData = new URLSearchParams();
      formData.append('username', registerEmail);
      formData.append('password', registerPassword);
      const res = await api.post('/auth/login', formData, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      });
      setAuth(res.data.access_token, { id: 0, nome: registerName, email: registerEmail });
      navigate('/home');
    } catch (err: any) {
      if (err.response?.data?.detail) {
        const detail = err.response.data.detail;
        if (Array.isArray(detail)) {
          setError(detail.map((e: any) => e.msg).join(', '));
        } else {
          setError(typeof detail === 'string' ? detail : JSON.stringify(detail));
        }
      } else {
        setError('Ocorreu um erro no cadastro. Tente novamente.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div 
      className="min-h-screen bg-black/50 bg-blend-overlay bg-cover bg-center flex items-center justify-center p-4 font-sans"
      style={{
        backgroundImage: 'url(https://assets.nflxext.com/ffe/siteui/vlv3/f841d4c7-10e1-40af-bcae-07a3f8dc141a/f6d7434e-d6de-4185-a6d4-c77a2d08737b/US-en-20220502-popsignuptwoweeks-perspective_alpha_website_medium.jpg)'
      }}
    >
      <div className={`auth-container ${isActive ? 'active' : ''}`} id="container">
        
        <div className="form-container sign-up">
            <form onSubmit={handleRegister}>
                <h1 className="text-white text-3xl font-bold">Criar Conta</h1>
                <div className="social-icons">
                    <button 
                      type="button"
                      onClick={handleGoogleLogin}
                      className="icon"
                      aria-label="Entrar com Google"
                    >
                      <svg viewBox="0 0 48 48" width="20" height="20">
                        <path fill="#4285F4" d="M45.12 24.5c0-2.6-.2-5.1-.7-7.5H24v9.2h11.5c-.5 2.7-2 5-4.2 6.5v5.4h6.8c4-3.7 6.8-9.2 6.8-15.6z"/>
                        <path fill="#34A853" d="M24 46c5.4 0 9.9-1.8 13.2-4.8l-6.8-5.4c-1.8 1.2-4.1 1.9-6.4 1.9-4.9 0-9.1-3.3-10.6-7.8H1.2v5.6C4.6 41.3 13.8 46 24 46z"/>
                        <path fill="#FBBC05" d="M13.4 28c1.3-1.9 2-4.2 2-6.5s-.7-4.6-2-6.5v-5.6H1.2C-.5 17.5 0 21.3 0 24s.5 6.5 1.2 9.4l6.2-5.4z"/>
                        <path fill="#EA4335" d="M24 10.2c2.7 0 5.1.9 7 2.6l5.8-5.6C33.1 3 29.4 1.5 24 1.5 13.8 1.5 4.6 6 1.2 14l6.2 5.6c1.5-4.5 5.7-7.9 10.6-7.9z"/>
                      </svg>
                    </button>
                </div>
                <span>use seu email para se registrar</span>
                
                {error && isActive && <div className="text-[#ffd700] text-sm my-2 text-left w-full">{error}</div>}

                <input type="text" placeholder="Nome" value={registerName} onChange={e => setRegisterName(e.target.value)} required />
                <input type="email" placeholder="Email" value={registerEmail} onChange={e => setRegisterEmail(e.target.value)} required />
                <input type="password" placeholder="Senha" value={registerPassword} onChange={e => setRegisterPassword(e.target.value)} required />
                <button type="submit" className="auth-btn" disabled={loading}>{loading ? 'Aguarde...' : 'Cadastrar'}</button>
            </form>
        </div>

        <div className="form-container sign-in">
            <form onSubmit={handleLogin}>
                <h1 className="text-white text-3xl font-bold">Entrar</h1>
                <div className="social-icons">
                    <button 
                      type="button"
                      onClick={handleGoogleLogin}
                      className="icon"
                      aria-label="Entrar com Google"
                    >
                      <svg viewBox="0 0 48 48" width="20" height="20">
                        <path fill="#4285F4" d="M45.12 24.5c0-2.6-.2-5.1-.7-7.5H24v9.2h11.5c-.5 2.7-2 5-4.2 6.5v5.4h6.8c4-3.7 6.8-9.2 6.8-15.6z"/>
                        <path fill="#34A853" d="M24 46c5.4 0 9.9-1.8 13.2-4.8l-6.8-5.4c-1.8 1.2-4.1 1.9-6.4 1.9-4.9 0-9.1-3.3-10.6-7.8H1.2v5.6C4.6 41.3 13.8 46 24 46z"/>
                        <path fill="#FBBC05" d="M13.4 28c1.3-1.9 2-4.2 2-6.5s-.7-4.6-2-6.5v-5.6H1.2C-.5 17.5 0 21.3 0 24s.5 6.5 1.2 9.4l6.2-5.4z"/>
                        <path fill="#EA4335" d="M24 10.2c2.7 0 5.1.9 7 2.6l5.8-5.6C33.1 3 29.4 1.5 24 1.5 13.8 1.5 4.6 6 1.2 14l6.2 5.6c1.5-4.5 5.7-7.9 10.6-7.9z"/>
                      </svg>
                    </button>
                </div>
                <span>ou use sua conta de email</span>
                
                {error && !isActive && <div className="text-[#FFD700] text-sm my-2 text-left w-full">{error}</div>}

                <input type="text" placeholder="E-mail ou Nome de Usuário" value={loginIdentifier} onChange={e => setLoginIdentifier(e.target.value)} required />
                <input type="password" placeholder="Senha" value={loginPassword} onChange={e => setLoginPassword(e.target.value)} required />
                <a href="#">Esqueceu a senha?</a>
                <button type="submit" className="auth-btn" disabled={loading}>{loading ? 'Aguarde...' : 'Entrar'}</button>
            </form>
        </div>

        <div className="toggle-container">
            <div className="toggle">
                <div className="toggle-panel toggle-left">
                    <h1 className="text-white text-3xl font-bold text-shadow">Bem-vindo de volta!</h1>
                    <p className="text-shadow">Acesse sua conta para continuar assistindo ao que você ama.</p>
                    <button type="button" className="auth-btn hidden-btn" onClick={() => handleToggle(false)}>Entrar</button>
                </div>
                <div className="toggle-panel toggle-right">
                    <h1 className="text-white text-3xl font-bold text-shadow">Comece sua jornada!!</h1>
                    <p className="text-shadow">Crie seu perfil e aproveite nossa plataforma para assistir seus conteudos favoritos.</p>
                    <button type="button" className="auth-btn hidden-btn" onClick={() => handleToggle(true)}>Cadastrar</button>
                </div>
            </div>
        </div>
        
      </div>
    </div>
  );
}
