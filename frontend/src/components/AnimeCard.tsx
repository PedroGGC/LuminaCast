import { useState } from "react";
import { Link } from "react-router-dom";
import { Play, Plus, Check, Star } from "lucide-react";
import type { Anime } from "../lib/api";
import { useMyListStore } from "../store/myListStore";

interface Props {
  anime: Anime & { subtitle?: string };
}

export default function AnimeCard({ anime }: Props) {
  const [hovered, setHovered] = useState(false);
  const myListIds = useMyListStore(state => state.items);
  const addToMyList = useMyListStore(state => state.add);
  const removeFromMyList = useMyListStore(state => state.remove);

  const isInList = myListIds.includes(anime.id);

  const handleListToggle = (e: React.MouseEvent) => {
    e.preventDefault();
    if (isInList) {
      removeFromMyList(anime.id);
    } else {
      addToMyList(anime.id);
    }
  };

  return (
    <div
      className="relative flex-shrink-0 w-[160px] sm:w-[200px] md:w-[240px] group"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Cover - Container com aspect-ratio forçado 2:3 */}
      <Link to={`/media/${anime.id}`} className="block">
        <div className="relative rounded-md overflow-hidden shadow-lg" style={{ aspectRatio: '2/3' }}>
          <img
            src={anime.poster_url || anime.cover_image || ""}
            alt={anime.title}
            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
          />
          {/* Hover overlay */}
          <div
            className={`absolute inset-0 bg-gradient-to-t from-black/90 via-black/30 to-transparent transition-opacity duration-300 ${
              hovered ? "opacity-100" : "opacity-0"
            }`}
          />
        </div>
      </Link>

      {/* Hover info card - com overflow hidden para não vazar botões */}
      <div
        className={`absolute left-0 right-0 p-3 transition-all duration-300 overflow-hidden ${
          hovered ? "opacity-100" : "opacity-0"
        }`}
        style={{ bottom: 0 }}
      >
        {/* 🎨 OPÇÕES DE ESTILO DO CARD (Basta trocar o className do div abaixo) 
            Acrylico (Blur): "bg-black/40 backdrop-blur-xl border border-white/10 shadow-2xl"
            Transparente: "bg-transparent"
            Sólido Escuro: "bg-lunima-dark/95" 
        */}
        <div className="bg-black/10 backdrop-blur-xl border border-white/10 shadow-2xl rounded-md p-3">
          <h3 className="text-sm font-semibold truncate">{anime.title}</h3>
          <div className="flex items-center gap-2 mt-1 text-xs text-lunima-light-gray">
            {anime.subtitle && <span className="text-lunima-gold font-medium">{anime.subtitle}</span>}
            {anime.rating && <><span className="text-green-400 font-medium">{Math.round(anime.rating * 10)}%</span><Star size={12} className="text-yellow-400" fill="currentColor" /></>}
            {!anime.subtitle && <span>{
              anime.media_type === 'anime' ? 'Anime' : 
              anime.media_type === 'movie' || anime.media_type === 'filme' ? 'Filme' : 
              'Desenho'
            }</span>}
          </div>

          <div className="flex items-center gap-2 mt-2">
            <Link
              to={`/media/${anime.id}`}
              className="w-7 h-7 flex items-center justify-center bg-white rounded-full hover:bg-white/80 transition"
              aria-label="Assistir"
            >
              <Play size={14} fill="black" className="text-black" />
            </Link>
            <button
              onClick={handleListToggle}
              className={`w-7 h-7 flex items-center justify-center border rounded-full transition ${isInList ? 'bg-white text-black border-white' : 'border-lunima-gray/60 text-white hover:border-white'}`}
              aria-label={isInList ? "Remover da lista" : "Adicionar à lista"}
            >
              {isInList ? <Check size={14} fill="currentColor" /> : <Plus size={14} />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
