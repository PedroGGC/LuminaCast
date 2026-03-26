import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, UserListResponse } from "../lib/api";
import { Play, X } from "lucide-react";
import { useMyListStore } from "../store/myListStore";

export default function MyList() {
  // We need the full objects. Let's fetch them here but keep store synced.
  const [fullItems, setFullItems] = useState<UserListResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const syncStore = useMyListStore(state => state.fetchList);
  const removeGlobal = useMyListStore(state => state.remove);

  useEffect(() => {
    loadMyList();
    syncStore(); // Refresh global list too
  }, []);

  const loadMyList = () => {
    setLoading(true);
    api
      .get<UserListResponse[]>("/api/my-list")
      .then((res) => setFullItems(res.data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  const handleRemove = async (mediaId: number) => {
    try {
      await removeGlobal(mediaId);
      setFullItems((prev) => prev.filter((i) => i.media_id !== mediaId));
    } catch {
      alert("Erro ao remover da lista");
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center pt-20">
        <div className="w-12 h-12 border-4 border-lunima-gold border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <main className="min-h-screen pt-24 px-6 lg:px-12 pb-20">
      <h1 className="text-2xl md:text-3xl font-bold mb-8 text-white">Minha Lista</h1>

      {error && <p className="text-red-400 mb-4">{error}</p>}

      {fullItems.length === 0 && !error ? (
        <div className="text-lunima-light-gray h-64 flex flex-col items-center justify-center border border-dashed border-gray-800 rounded-xl gap-3">
          <p className="text-lg">Você ainda não adicionou títulos à sua lista.</p>
          <Link to="/" className="text-lunima-gold hover:underline text-sm">
            Explorar catálogo →
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {fullItems.map((item) => (
            <div key={item.id} className="relative group">
              <Link to={`/media/${item.media_id}`} className="block">
                <div className="relative aspect-[2/3] rounded-lg overflow-hidden shadow-lg bg-zinc-900">
                  {item.media.poster_url ? (
                    <img
                      src={item.media.poster_url}
                      alt={item.media.title}
                      className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-zinc-600 text-xs text-center p-2">
                      {item.media.title}
                    </div>
                  )}
                  <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                </div>
              </Link>

              {/* Overlay buttons */}
              <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                <Link
                  to={`/media/${item.media_id}`}
                  className="w-9 h-9 flex items-center justify-center bg-white rounded-full hover:bg-white/80 transition"
                  aria-label="Assistir"
                >
                  <Play size={15} fill="black" className="text-black" />
                </Link>
                <button
                  className="w-9 h-9 flex items-center justify-center border border-white bg-black/50 text-white rounded-full hover:bg-red-600 hover:border-red-600 transition"
                  title="Remover da lista"
                  onClick={() => handleRemove(item.media_id)}
                >
                  <X size={15} />
                </button>
              </div>

              {/* Title below */}
              <p className="mt-2 text-xs text-zinc-300 truncate px-0.5">{item.media.title}</p>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
