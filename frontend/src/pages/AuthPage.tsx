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
                      <img src="/google_colorido.svg" alt="Google" className="w-5 h-5" />
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
                      <img src="/google_colorido.svg" alt="Google" className="w-5 h-5" />
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
