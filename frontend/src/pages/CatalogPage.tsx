import { useEffect, useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { api, Anime } from "../lib/api";
import { useMyListStore } from "../store/myListStore";

interface Props {
  type: "anime" | "desenho";
}

const GENRES = [
  "Ação",
  "Aventura",
  "Comédia",
  "Drama",
  "Fantasia",
  "Romance",
  "Sci-Fi",
  "Suspense",
];

// Map genre labels to English keywords for broader matching against synopsis/title
const GENRE_KEYWORDS: Record<string, string[]> = {
  "Ação": ["action", "ação", "luta", "batalha", "combat"],
  "Aventura": ["adventure", "aventura", "jornada", "quest"],
  "Comédia": ["comedy", "comédia", "humor", "funny"],
  "Drama": ["drama", "emotional", "emocional"],
  "Fantasia": ["fantasy", "fantasia", "magic", "magia", "mágico"],
  "Romance": ["romance", "love", "amor"],
  "Sci-Fi": ["sci-fi", "science fiction", "ficção científica", "scifi", "future", "futuro", "espaço", "space"],
  "Suspense": ["thriller", "suspense", "mystery", "mistério", "horror", "terror"],
};

export default function CatalogPage({ type }: Props) {
  const [items, setItems] = useState<Anime[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedGenre, setSelectedGenre] = useState<string | null>(null);

  const fetchMyList = useMyListStore((state) => state.fetchList);

  const pageTitle = type === "anime" ? "Animes" : "Desenhos";
  const endpoint = type === "anime" ? "/api/media/animes" : "/api/media/desenhos";

  useEffect(() => {
    fetchMyList();
    setLoading(true);
    setError(null);
    api
      .get<Anime[]>(endpoint)
      .then((res) => setItems(res.data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [type, endpoint, fetchMyList]);

  const filteredItems = useMemo(() => {
    if (!selectedGenre) return items;
    const keywords = GENRE_KEYWORDS[selectedGenre] || [selectedGenre.toLowerCase()];
    return items.filter((item) => {
      const hay = `${item.title} ${item.synopsis || ""}`.toLowerCase();
      return keywords.some((kw) => hay.includes(kw));
    });
  }, [items, selectedGenre]);

  return (
    <main className="min-h-screen pt-24 px-6 lg:px-12 pb-20">
      {/* Header */}
      <div className="flex items-baseline gap-4 mb-6">
        <h1 className="text-3xl md:text-4xl font-bold text-white">{pageTitle}</h1>
        <span className="text-lunima-gray text-sm">
          {loading ? "Carregando..." : `${filteredItems.length} títulos`}
        </span>
      </div>

      {/* Genre pill selector */}
      <div className="flex flex-wrap gap-2 mb-8">
        <button
          onClick={() => setSelectedGenre(null)}
          className={`px-4 py-1.5 rounded-full text-sm font-medium border transition ${
            selectedGenre === null
              ? "bg-lunima-gold text-black border-lunima-gold"
              : "border-white/20 text-lunima-light-gray hover:border-white/50 hover:text-white"
          }`}
        >
          Todos
        </button>
        {GENRES.map((genre) => (
          <button
            key={genre}
            onClick={() => setSelectedGenre(selectedGenre === genre ? null : genre)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium border transition ${
              selectedGenre === genre
                ? "bg-lunima-gold text-black border-lunima-gold"
                : "border-white/20 text-lunima-light-gray hover:border-white/50 hover:text-white"
            }`}
          >
            {genre}
          </button>
        ))}
      </div>

      {/* Error state */}
      {error && (
        <div className="text-red-400 text-sm bg-red-500/10 border border-red-500/30 rounded-lg p-4 mb-6">
          Erro ao carregar catálogo: {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {Array.from({ length: 18 }).map((_, i) => (
            <div
              key={i}
              className="aspect-[2/3] rounded-lg bg-zinc-900 animate-pulse"
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && filteredItems.length === 0 && !error && (
        <div className="flex flex-col items-center justify-center h-64 text-lunima-gray border border-dashed border-white/10 rounded-xl gap-3">
          <p className="text-lg">
            {selectedGenre
              ? `Nenhum título encontrado para "${selectedGenre}".`
              : "Nenhum título disponível."}
          </p>
          {selectedGenre && (
            <button
              onClick={() => setSelectedGenre(null)}
              className="text-lunima-gold hover:underline text-sm"
            >
              Limpar filtro
            </button>
          )}
        </div>
      )}

      {/* Media grid */}
      {!loading && filteredItems.length > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {filteredItems.map((item) => (
            <Link key={item.id} to={`/media/${item.id}`} className="block group">
              <div className="relative aspect-[2/3] rounded-lg overflow-hidden shadow-lg bg-zinc-900">
                {item.poster_url ? (
                  <img
                    src={item.poster_url}
                    alt={item.title}
                    className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-zinc-500 text-xs text-center p-2 bg-zinc-800">
                    {item.title}
                  </div>
                )}
                {/* Hover overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
                {/* Type badge */}
                <div className="absolute top-2 left-2 opacity-0 group-hover:opacity-100 transition-opacity">
                  <span className="text-[10px] bg-black/60 text-lunima-gold px-1.5 py-0.5 rounded border border-lunima-gold/40 font-medium">
                    {item.media_type === "anime" ? "Anime" : "Desenho"}
                  </span>
                </div>
              </div>
              <p className="mt-2 text-xs text-zinc-300 truncate px-0.5 group-hover:text-white transition">
                {item.title}
              </p>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
