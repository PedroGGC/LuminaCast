import { useEffect, useState } from "react";
import { api, Anime } from "../lib/api";
import HeroBanner from "../components/HeroBanner";
import AnimeCarousel from "../components/AnimeCarousel";
import { useMyListStore } from "../store/myListStore";

interface HistoryItem {
  media_id: string;
  media_type: string;
  last_episode: number;
  title: string;
  poster_url: string | null;
}

interface CarouselItem {
  id: string;
  mal_id?: number;
  tmdb_id?: number;
  title: string;
  poster_url: string | null;
  score?: number;
  year?: string;
}

interface Carousel {
  title: string;
  type: string;
  items: CarouselItem[];
}

export default function Home() {
  const [carousels, setCarousels] = useState<Carousel[]>([]);
  const [featured, setFeatured] = useState<Anime | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<HistoryItem[]>([]);

  const fetchMyList = useMyListStore(state => state.fetchList);

  useEffect(() => {
    setLoading(true);
    fetchMyList();

    const fetchDatas = async () => {
      try {
        // Busca histórico em paralelo
        const historyPromise = api.get("/api/history").catch(() => ({ data: [] }));
        
        // Consome a API /api/home com carrosséis dinâmicos
        const response = await api.get("/api/home");
        const data = response.data;
        
        // Processa histórico
        const historyRes = await historyPromise;
        if (historyRes.data && historyRes.data.length > 0) {
          setHistory(historyRes.data);
        }

        if (data.carousels && data.carousels.length > 0) {
          setCarousels(data.carousels);
          
          // Seleciona um item aleatório para o Hero Banner
          const allItems = data.carousels.flatMap((c: Carousel) => c.items);
          if (allItems.length > 0) {
            const randomItem = allItems[Math.floor(Math.random() * allItems.length)];
            const prefixedId = (randomItem.type === 'anime') 
              ? `mal_${randomItem.mal_id || randomItem.tmdb_id || 0}` 
              : `tmdb_${randomItem.tmdb_id || randomItem.mal_id || 0}`;
            
            setFeatured({
              id: prefixedId,
              title: randomItem.title,
              poster_url: randomItem.poster_url,
              cover_image: randomItem.poster_url,
              synopsis: "",
              media_type: randomItem.type === 'anime' ? 'anime' : 'desenho',
            });
          }
        }
      } catch (e: any) {
        console.error("Erro ao carregar home:", e);
        setError(e.message);
      } finally {
        setLoading(false);
      }
    };

    fetchDatas();
  }, [fetchMyList]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-lunima-gold border-t-transparent rounded-full animate-spin" />
          <span className="text-lunima-light-gray text-sm">Carregando catálogo...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <p className="text-lunima-gold text-xl font-bold">Ops!</p>
          <p className="text-lunima-light-gray">Não foi possível carregar o catálogo.</p>
          <p className="text-lunima-gray text-sm">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-4 px-6 py-2 bg-lunima-gold hover:bg-lunima-gold-hover rounded text-sm font-semibold transition"
          >
            Tentar novamente
          </button>
        </div>
      </div>
    );
  }

  // Converte os dados da API home para o formato esperado pelo AnimeCarousel
  const categories = carousels.map((carousel) => ({
    id: carousel.title,
    name: carousel.title,
    slug: carousel.type,
    animes: carousel.items.map((item) => {
      const type = carousel.type === 'anime' ? 'anime' : 'desenho';
      const prefixedId = type === 'anime' ? `mal_${item.mal_id || 0}` : `tmdb_${item.tmdb_id || 0}`;
      return {
        id: prefixedId,
        title: item.title,
        poster_url: item.poster_url,
        cover_image: item.poster_url,
        synopsis: "",
        media_type: type,
        rating: item.score,
      };
    }),
  }));

  // Converte histórico para formato de anime (com subtítulo do episódio)
  const historyAnimes = history.map((item) => {
    const type = item.media_type === 'anime' ? 'anime' : 'desenho';
    const prefix = type === 'anime' ? 'mal_' : 'tmdb_';
    return {
      id: `${prefix}${item.media_id.replace(prefix, '')}`,
      title: item.title,
      poster_url: item.poster_url,
      cover_image: item.poster_url,
      synopsis: "",
      media_type: type,
      subtitle: `Episódio ${item.last_episode}`,
    };
  });

  return (
    <main>
      {featured && <HeroBanner anime={featured} />}

      <div className="-mt-16 relative z-10 space-y-2 pb-16">
        {historyAnimes.length > 0 && (
          <AnimeCarousel title="Continuar Assistindo" animes={historyAnimes} />
        )}
        {categories.map((cat) => (
          <AnimeCarousel key={cat.id} title={cat.name} animes={cat.animes} />
        ))}
      </div>
    </main>
  );
}