import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Anime } from "../lib/api";
import { searchAnimes } from "../lib/api";
import AnimeCard from "../components/AnimeCard";

export default function Search() {
  const [searchParams] = useSearchParams();
  const query = searchParams.get("q") || "";
  const [results, setResults] = useState<Anime[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!query) {
      setResults([]);
      return;
    }

    setLoading(true);
    searchAnimes(query)
      .then((data) => setResults(data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [query]);

  return (
    <main className="min-h-screen pt-24 px-6 lg:px-12 bg-lunima-black">
      <h1 className="text-2xl md:text-3xl font-bold mb-6 text-white">
        Resultados para "{query}"
      </h1>

      {loading && (
        <div className="flex items-center justify-center h-32">
          <div className="w-8 h-8 border-4 border-lunima-gold border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {error && <p className="text-lunima-gold">{error}</p>}

      {!loading && !error && results.length === 0 && query && (
        <div className="text-lunima-light-gray h-64 flex flex-col items-center justify-center">
          <p className="text-lg">Sua busca por "{query}" não encontrou correspondências.</p>
          <p className="text-sm mt-2">Sugestões:</p>
          <ul className="list-disc mt-2 text-sm">
            <li>Tente palavras-chave diferentes</li>
            <li>Procurando por um filme ou programa de TV?</li>
            <li>Tente usar o título de um anime ou desenho</li>
          </ul>
        </div>
      )}

      {!loading && !error && results.length > 0 && (
        <div className="flex flex-wrap gap-4">
          {results.map((anime) => (
            <AnimeCard key={anime.id} anime={anime} />
          ))}
        </div>
      )}
    </main>
  );
}
