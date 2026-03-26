import { useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import type { Anime } from "../lib/api";
import AnimeCard from "./AnimeCard";

interface Props {
  title: string;
  animes: (Anime & { subtitle?: string })[];
}

export default function AnimeCarousel({ title, animes }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(true);

  const checkScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 10);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 10);
  };

  const scroll = (direction: "left" | "right") => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.clientWidth * 0.8;
    el.scrollBy({
      left: direction === "left" ? -distance : distance,
      behavior: "smooth",
    });
    setTimeout(checkScroll, 400);
  };

  if (animes.length === 0) return null;

  return (
    <section className="relative px-6 lg:px-12 py-4 group/carousel">
      <h2 className="text-lg md:text-xl font-bold mb-3 text-white/90">{title}</h2>

      {/* Left arrow */}
      {canScrollLeft && (
        <button
          onClick={() => scroll("left")}
          className="absolute left-0 top-1/2 translate-y-2 z-10 w-10 h-28 flex items-center justify-center bg-black/60 hover:bg-black/80 transition opacity-0 group-hover/carousel:opacity-100"
          aria-label="Scroll left"
        >
          <ChevronLeft size={28} />
        </button>
      )}

      {/* Cards */}
      <div
        ref={scrollRef}
        onScroll={checkScroll}
        className="flex gap-3 overflow-x-auto scrollbar-thin pb-2"
        style={{ scrollbarWidth: "none", msOverflowStyle: "none" }}
      >
        {animes.map((anime) => (
          <AnimeCard key={anime.id} anime={anime} />
        ))}
      </div>

      {/* Right arrow */}
      {canScrollRight && (
        <button
          onClick={() => scroll("right")}
          className="absolute right-0 top-1/2 translate-y-2 z-10 w-10 h-28 flex items-center justify-center bg-black/60 hover:bg-black/80 transition opacity-0 group-hover/carousel:opacity-100"
          aria-label="Scroll right"
        >
          <ChevronRight size={28} />
        </button>
      )}
    </section>
  );
}
