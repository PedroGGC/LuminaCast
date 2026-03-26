import { Link } from "react-router-dom";
import { Play, Info } from "lucide-react";
import type { Anime } from "../lib/api";

interface Props {
  anime: Anime;
}

export default function HeroBanner({ anime }: Props) {
  return (
    <section className="relative w-full h-[85vh] min-h-[500px] flex items-end">
      {/* Background image */}
      <div className="absolute inset-0">
        <img
          src={anime.poster_url || anime.banner_image || ""}
          alt={anime.title}
          className="w-full h-full object-cover"
        />
        {/* Gradient overlays */}
        <div className="absolute inset-0 bg-gradient-to-t from-lunima-black via-lunima-black/40 to-transparent" />
        <div className="absolute inset-0 bg-gradient-to-r from-lunima-black/80 via-transparent to-transparent" />
      </div>

      {/* Content */}
      <div className="relative z-10 max-w-2xl px-6 lg:px-12 pb-20">
        {/* Acrylic / Glassmorphism info box */}
        <div
          style={{
            backgroundColor: "rgba(0, 0, 0, 0.45)",
            backdropFilter: "blur(14px)",
            WebkitBackdropFilter: "blur(14px)",
          }}
          className="space-y-4 rounded-xl p-6 border border-white/10 shadow-2xl"
        >
          <h1 className="text-4xl md:text-6xl font-extrabold leading-tight drop-shadow-lg">
            {anime.title}
          </h1>

          <div className="flex items-center gap-3 text-sm text-lunima-light-gray">
            <span className="text-green-400 font-semibold">Novo</span>
            <span className="border border-lunima-gray px-1.5 py-0.5 text-xs rounded">
              {anime.media_type === "anime" ? "Anime" : "Desenho"}
            </span>
          </div>

          <p className="text-base md:text-lg text-lunima-light-gray line-clamp-3 leading-relaxed">
            {anime.synopsis}
          </p>

          <div className="flex items-center gap-3 pt-1">
            <Link
              to={`/media/${anime.id}`}
              className="flex items-center gap-2 bg-white text-black font-semibold px-6 py-2.5 rounded hover:bg-white/80 transition text-sm"
            >
              <Play size={18} fill="black" /> Assistir
            </Link>
            <Link
              to={`/media/${anime.id}`}
              className="flex items-center gap-2 bg-lunima-gray/40 text-white font-semibold px-6 py-2.5 rounded hover:bg-lunima-gray/60 transition text-sm backdrop-blur-sm"
            >
              <Info size={18} /> Mais Info
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
