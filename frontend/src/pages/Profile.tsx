import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuthStore } from "../store/authStore";

interface ProfileForm {
  nome: string;
  email: string;
}

export default function Profile() {
  const { user, setAuth, token } = useAuthStore();
  const navigate = useNavigate();
  const [form, setForm] = useState<ProfileForm>({
    nome: user?.nome ?? "",
    email: user?.email ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((prev) => ({ ...prev, [e.target.name]: e.target.value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setMessage(null);
    try {
      await api.put("/auth/me", { nome: form.nome, email: form.email });
      // Update local store with new name
      if (token && user) {
        setAuth(token, { ...user, nome: form.nome, email: form.email });
      }
      setMessage({ type: "success", text: "Perfil atualizado com sucesso!" });
    } catch (e: any) {
      setMessage({
        type: "error",
        text: e.response?.data?.detail ?? "Erro ao atualizar perfil.",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <main className="min-h-screen pt-28 px-6 lg:px-12 pb-20 flex items-start justify-center">
      <div className="w-full max-w-md">
        {/* Avatar */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-20 h-20 rounded-full bg-gradient-to-br from-lunima-gold to-yellow-600 flex items-center justify-center text-3xl font-extrabold text-black shadow-lg mb-3">
            {user?.nome?.charAt(0).toUpperCase() ?? "?"}
          </div>
          <p className="text-white font-bold text-xl">{user?.nome}</p>
          <p className="text-zinc-400 text-sm">{user?.email}</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 space-y-4">
          <h2 className="text-white font-semibold text-lg mb-2">Editar Perfil</h2>

          <div>
            <label className="block text-zinc-400 text-sm mb-1">Nome</label>
            <input
              type="text"
              name="nome"
              value={form.nome}
              onChange={handleChange}
              required
              className="w-full bg-zinc-800 border border-zinc-600 text-white rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-yellow-500/50 focus:border-yellow-500 transition"
            />
          </div>

          <div>
            <label className="block text-zinc-400 text-sm mb-1">E-mail</label>
            <input
              type="email"
              name="email"
              value={form.email}
              onChange={handleChange}
              required
              className="w-full bg-zinc-800 border border-zinc-600 text-white rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-yellow-500/50 focus:border-yellow-500 transition"
            />
          </div>

          {message && (
            <p className={`text-sm ${message.type === "success" ? "text-green-400" : "text-red-400"}`}>
              {message.text}
            </p>
          )}

          <button
            type="submit"
            disabled={saving}
            className="w-full bg-lunima-gold text-black font-bold py-2.5 rounded-lg hover:bg-lunima-gold-hover transition disabled:opacity-50"
          >
            {saving ? "Salvando..." : "Salvar alterações"}
          </button>
        </form>

        <button
          onClick={() => navigate(-1)}
          className="mt-4 w-full text-center text-zinc-500 hover:text-zinc-300 text-sm transition"
        >
          ← Voltar
        </button>
      </div>
    </main>
  );
}
