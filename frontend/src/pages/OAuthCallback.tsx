import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { useAuthStore } from '../store/authStore'

export default function OAuthCallback() {
  const navigate = useNavigate()
  const setAuth = useAuthStore((state) => state.setAuth)

  useEffect(() => {
    const handleOAuthCallback = async () => {
      const { data: { session }, error } = await supabase.auth.getSession()

      if (error || !session) {
        console.error('Erro ao obter sessão:', error)
        navigate('/login')
        return
      }

      const { access_token, user } = session
      
      setAuth(access_token, {
        id: 0,
        nome: user?.user_metadata?.full_name || user?.email?.split('@')[0] || 'Usuário',
        email: user?.email || ''
      })

      navigate('/home')
    }

    handleOAuthCallback()
  }, [])

  return (
    <div className="min-h-screen bg-lunima-black flex items-center justify-center">
      <div className="text-center">
        <div className="w-12 h-12 border-4 border-lunima-gold border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-lunima-light-gray">Processando login...</p>
      </div>
    </div>
  )
}