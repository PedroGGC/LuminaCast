import { useState, useEffect, useMemo } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Play,
  Star,
  Calendar,
  Film,
  Download,
  Loader2,
  Plus,
  Check,
  HelpCircle,
} from "lucide-react";
import { api, MediaEpisode, AnimeDetail as AnimeDetailType } from "../lib/api";
import { useMyListStore } from "../store/myListStore";
import { useAuthStore } from "../store/authStore";

// ─── Helper: download com progresso ─────────────────────────────────────────
async function downloadWithProgress(
  url: string, 
  filename: string, 
  onProgress: (progress: number) => void
) {
  const token = useAuthStore.getState().token;
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  
  const response = await fetch(url, { 
    credentials: "include",
    headers 
  });
  if (!response.ok) throw new Error("Download failed");
  
  const reader = response.body?.getReader();
  if (!reader) throw new Error("No reader");
  
  const headerContentLength = response.headers.get("Content-Length");
  const contentLength = headerContentLength ? +headerContentLength : 0;
  let receivedLength = 0;
  const chunks: any[] = [];
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    receivedLength += value.length;
    if (contentLength > 0) {
      onProgress(Math.round((receivedLength / contentLength) * 100));
    }
  }
  
  const blob = new Blob(chunks as BlobPart[]);
  const blobUrl = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.setAttribute("download", filename);
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(blobUrl);
}

export default function AnimeDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [anime, setAnime] = useState<AnimeDetailType | null>(null);
  const [episodes, setEpisodes] = useState<MediaEpisode[]>([]);
  const [loading, setLoading] = useState(true);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSeason, setSelectedSeason] = useState<number>(1);

  // Download range
  const [rangeFrom, setRangeFrom] = useState<number>(1);
  const [rangeTo, setRangeTo] = useState<number>(1);
  const [isBatchDownloading, setIsBatchDownloading] = useState(false);
  const [batchDownloadComplete, setBatchDownloadComplete] = useState(false);

  // Per-episode download state: 'downloading' | 'complete' | undefined
  const [downloadState, setDownloadState] = useState<Record<number, 'downloading' | 'complete'>>({});

  // Download availability check (background)
  const [canDownload, setCanDownload] = useState(true);

  // Minha Lista state
  const myListIds = useMyListStore((state) => state.items);
  const addToMyList = useMyListStore((state) => state.add);
  const [listStatus, setListStatus] = useState<"idle" | "adding" | "added">("idle");

  // Watch history state
  const [watchedEpisodes, setWatchedEpisodes] = useState<number[]>([]);
  const [hoveredWatchedEp, setHoveredWatchedEp] = useState<number | null>(null);

  // Sync with global store
  useEffect(() => {
    if (id && myListIds.includes(Number(id))) {
      setListStatus("added");
    } else {
      setListStatus("idle");
    }
  }, [id, myListIds]);

  // ─── Fetch media details and episodes ───────────────────────────────────────
  useEffect(() => {
    if (!id) return;

    const fetchData = async () => {
      setLoading(true);
      setIsInitialLoading(true);
      setAnime(null);
      setEpisodes([]);
      setError(null);

      try {
        // Endpoint otimizado: carrega tudo de uma vez (evita race conditions)
        const fullRes = await api.get(`/api/media/${id}/full`);
        const { media, episodes, can_download } = fullRes.data;

        setAnime({ ...media, episodes: [] });
        setEpisodes(episodes);
        setCanDownload(can_download);

        // Busca histórico de episódios assistidos
        const mediaId = media.external_id || id;
        try {
          const historyRes = await api.get(`/api/history/${mediaId}`);
          if (historyRes.data && historyRes.data.watched_episodes) {
            setWatchedEpisodes(historyRes.data.watched_episodes);
          }
        } catch (e) {
          console.error("Erro ao buscar histórico:", e);
        }

        if (episodes.length > 0) {
          const firstSeason = Math.min(...episodes.map((e: MediaEpisode) => e.season_number));
          setSelectedSeason(firstSeason);
        }
      } catch (e: any) {
        console.error("Erro ao carregar dados:", e);
        setError(e.message);
      } finally {
        setLoading(false);
        setIsInitialLoading(false);
      }
    };

    fetchData();
  }, [id]);

  // Group episodes by season
  const episodesBySeason = useMemo(() => {
    const map: Record<number, MediaEpisode[]> = {};
    episodes.forEach((ep) => {
      if (!map[ep.season_number]) map[ep.season_number] = [];
      map[ep.season_number].push(ep);
    });
    return map;
  }, [episodes]);

  const seasonNumbers = useMemo(() => {
    return Object.keys(episodesBySeason)
      .map(Number)
      .sort((a, b) => a - b);
  }, [episodesBySeason]);

  const currentSeasonEpisodes = useMemo(() => {
    return (episodesBySeason[selectedSeason] || []).sort((a, b) => a.episode_number - b.episode_number);
  }, [episodesBySeason, selectedSeason]);

  useEffect(() => {
    if (currentSeasonEpisodes.length > 0) {
      setRangeFrom(1);
      setRangeTo(currentSeasonEpisodes.length);
    }
  }, [currentSeasonEpisodes]);

  const maxEpInSeason = currentSeasonEpisodes.length;
  const rangeError = rangeTo > maxEpInSeason;

  // ─── Handlers ───────────────────────────────────────────────────────────
  const handleBatchDownload = async () => {
    if (rangeError || rangeFrom > rangeTo || isBatchDownloading) return;

    const epIds = currentSeasonEpisodes
      .filter((e) => e.episode_number >= rangeFrom && e.episode_number <= rangeTo)
      .map((e) => e.id);

    if (epIds.length === 0) {
      alert("Nenhum episódio no intervalo selecionado.");
      return;
    }

    setIsBatchDownloading(true);
    try {
      const fname = `${anime?.title || "episodios"}_${rangeFrom}-${rangeTo}.zip`;
      await downloadWithProgress(`/api/download-batch?episode_ids=${epIds.join(",")}`, fname, () => {});
      setBatchDownloadComplete(true);
      setTimeout(() => setBatchDownloadComplete(false), 10000);
    } catch {
      alert("Erro ao baixar episódios.");
    } finally {
      setIsBatchDownloading(false);
    }
  };

  const handleSingleDownload = async (ep: MediaEpisode) => {
    if (downloadState[ep.id]) return;
    setDownloadState((prev) => ({ ...prev, [ep.id]: 'downloading' }));
    try {
      const cleanTitle = (ep.title || "Sem_Titulo").replace(/[^a-zA-Z0-9 _]/g, "").replace(/ /g, "_");
      const fname = `S${String(ep.season_number).padStart(2, "0")}E${String(ep.episode_number).padStart(2, "0")}_${cleanTitle}.mp4`;
      await downloadWithProgress(`/api/download/episode/${ep.id}`, fname, () => {});
      setDownloadState((prev) => ({ ...prev, [ep.id]: 'complete' }));
      setTimeout(() => {
        setDownloadState((prev) => {
          const { [ep.id]: _, ...rest } = prev;
          return rest;
        });
      }, 10000);
    } catch {
      alert("Erro ao baixar episódio.");
      setDownloadState((prev) => {
        const { [ep.id]: _, ...rest } = prev;
        return rest;
      });
    }
  };

  const handleAddToList = async () => {
    if (!anime || listStatus !== "idle") return;
    setListStatus("adding");
    try {
      // Use anime.id (the real integer PK from the DB), NOT Number(id) from the URL
      // URL params can be prefixed strings like "mal_12345" — Number() would return NaN
      await addToMyList(anime.id as number);
      setListStatus("added");
    } catch (e) {
      setListStatus("idle");
    }
  };

  if (isInitialLoading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center bg-lunima-black">
        <div className="w-12 h-12 border-4 border-lunima-gold border-t-transparent rounded-full animate-spin mb-4" />
        <p className="text-lunima-light-gray text-sm">Carregando informações da mídia...</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-lunima-gold border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !anime) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center space-y-4">
          <p className="text-lunima-gold text-xl font-bold">Erro</p>
          <p className="text-lunima-light-gray">{error ?? "Mídia não encontrada"}</p>
          <Link to="/" className="inline-flex items-center gap-2 mt-4 px-6 py-2 bg-lunima-gold hover:bg-lunima-gold-hover rounded text-sm font-semibold transition">
            <ArrowLeft size={16} /> Voltar
          </Link>
        </div>
      </div>
    );
  }

  return (
    <main className="pb-24">
      <section className="relative w-full h-[60vh] min-h-[400px]">
        <img
          src={anime.poster_url || anime.banner_image || anime.cover_image || ""}
          alt={anime.title}
          className="w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-lunima-black via-lunima-black/50 to-transparent" />
        <div className="absolute inset-0 bg-gradient-to-r from-lunima-black/70 via-transparent to-transparent" />
        <button
          onClick={() => navigate("/")}
          className="absolute top-24 left-6 lg:left-12 z-20 flex items-center gap-2 text-sm text-lunima-light-gray hover:text-white transition"
        >
          <ArrowLeft size={18} /> Voltar
        </button>
      </section>

      <div className="relative -mt-40 z-10 px-6 lg:px-12 pb-16 max-w-5xl">
        <h1 className="text-3xl md:text-5xl font-extrabold mb-4 drop-shadow-lg">{anime.title}</h1>

        <div className="flex flex-wrap items-center gap-4 text-sm text-lunima-light-gray mb-6">
          {anime.rating && <span className="text-green-400 font-semibold">{Math.round(anime.rating * 10)}% Match</span>}
          {anime.year && <span className="flex items-center gap-1"><Calendar size={14} /> {anime.year}</span>}
          <span className="flex items-center gap-1">
            <Film size={14} /> 
            {
              anime.media_type === "anime" ? "Anime" : 
              anime.media_type === "movie" || anime.media_type === "filme" ? "Filme" : 
              "Desenho"
            }
          </span>
          {anime.rating && <span className="flex items-center gap-1"><Star size={14} className="text-yellow-400" fill="currentColor" /> {anime.rating.toFixed(1)}</span>}
        </div>

        <p className="text-base md:text-lg text-lunima-light-gray leading-relaxed mb-4 max-w-3xl">{anime.synopsis}</p>

        <div className="flex items-center gap-3 mb-10">
          <button
            onClick={handleAddToList}
            disabled={listStatus !== "idle"}
            className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold border transition ${
              listStatus === "added" ? "border-lunima-gold text-lunima-gold bg-lunima-gold/10 cursor-default" : "border-white/30 text-white hover:border-white/60 hover:bg-white/10"
            }`}
          >
            {listStatus === "adding" ? <><Loader2 size={15} className="animate-spin" /> Adicionando...</> : 
             listStatus === "added" ? <><Check size={15} /> Na minha lista</> : 
             <><Plus size={15} /> Adicionar à lista</>}
          </button>
        </div>

        {episodes.length > 0 && (
          <section>
            <div className="flex flex-col sm:flex-row sm:items-center gap-4 mb-4">
              <h2 className="text-xl font-bold">Episódios</h2>
              {seasonNumbers.length > 1 && (
                <select
                  value={selectedSeason}
                  onChange={(e) => setSelectedSeason(Number(e.target.value))}
                  className="bg-zinc-900 border border-zinc-700 text-white text-sm rounded-lg px-3 py-2 cursor-pointer outline-none hover:border-lunima-gold transition"
                >
                  {seasonNumbers.map((s) => <option key={s} value={s}>Temporada {s}</option>)}
                </select>
              )}
              <span className="text-lunima-gray text-sm">{currentSeasonEpisodes.length} episódio{currentSeasonEpisodes.length !== 1 ? "s" : ""}</span>
            </div>

            {!canDownload && (
              <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 mb-6">
                <p className="text-amber-400 text-sm font-medium">
                  ⚠️ Os downloads estão temporariamente indisponíveis para os episódios desta obra.
                </p>
              </div>
            )}

            <div className="bg-zinc-900 border border-zinc-700 rounded-xl p-5 mb-6">
              <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">
                <Download size={14} className="inline mr-1.5 -mt-0.5" /> Download de Temporada
              </h3>
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-sm text-zinc-300">Do episódio</span>
                <input
                  type="number" min={1} max={maxEpInSeason} value={rangeFrom}
                  onChange={(e) => setRangeFrom(Number(e.target.value) || 1)}
                  onFocus={(e) => e.target.select()}
                  className="w-16 bg-zinc-800 border border-zinc-600 text-white text-sm text-center rounded-lg px-2 py-1.5 outline-none focus:ring-2 focus:ring-yellow-500/50 focus:border-yellow-500 transition"
                  disabled={!canDownload}
                />
                <span className="text-sm text-zinc-300">até o</span>
                <input
                  type="number" min={1} value={rangeTo}
                  onChange={(e) => setRangeTo(Number(e.target.value) || 1)}
                  onFocus={(e) => e.target.select()}
                  className={`w-16 bg-zinc-800 border text-white text-sm text-center rounded-lg px-2 py-1.5 outline-none focus:ring-2 transition ${rangeError ? "border-red-500 focus:ring-red-500/50" : "border-zinc-600 focus:ring-yellow-500/50 focus:border-yellow-500"} ${!canDownload ? "opacity-50" : ""}`}
                  disabled={!canDownload}
                />
                <button
                  onClick={handleBatchDownload}
                  disabled={!canDownload || rangeError || rangeFrom > rangeTo || isBatchDownloading}
                  className={`flex items-center gap-2 text-sm font-bold px-5 py-2 rounded-lg transition disabled:opacity-40 ${canDownload ? "bg-lunima-gold text-black hover:bg-lunima-gold-hover" : "bg-zinc-700 text-zinc-400 cursor-not-allowed"}`}
                >
                  {batchDownloadComplete ? <><Check size={14} /> Concluído!</> : isBatchDownloading ? <><Loader2 size={14} className="animate-spin" /> Baixando...</> : <><Download size={14} /> Baixar</>}
                </button>
              </div>
              {rangeError && <p className="text-red-500 text-xs mt-2">O último episódio desta temporada é o {maxEpInSeason}</p>}
            </div>

            <div className="flex flex-col gap-2">
              {currentSeasonEpisodes.map((ep) => {
                const state = downloadState[ep.id];
                const isWatched = watchedEpisodes.includes(ep.episode_number);
                return (
                  <div key={ep.id} className={`flex items-center gap-4 rounded-lg overflow-hidden transition group border ${isWatched ? 'bg-white/5 border-white/10 opacity-60' : 'bg-white/5 hover:bg-white/10 border-white/5'}`}>
                    <div className="relative flex-shrink-0 w-40 aspect-video bg-zinc-900 overflow-hidden">
                      <img src={ep.thumbnail_url || ""} alt={ep.title || ""} className="w-full h-full object-cover" onError={(e) => {(e.target as HTMLImageElement).style.display = "none";}} />
                    </div>
                    <div className="flex-1 py-3 pr-4 min-w-0">
                      <p className={`text-xs font-semibold mb-0.5 ${isWatched ? 'text-lunima-gray' : 'text-lunima-gold'}`}>S{ep.season_number} · EP {ep.episode_number}{isWatched && ' · Assistido'}</p>
                      <p className="text-sm text-white font-medium truncate">{ep.title || `Episódio ${ep.episode_number}`}</p>
                    </div>
                    <div className="flex items-center gap-2 mr-4 flex-shrink-0">
                      {isWatched ? (
                        <div 
                          className="w-9 h-9 flex items-center justify-center border border-green-500/50 rounded-full cursor-pointer group/play-btn relative"
                          onMouseEnter={() => setHoveredWatchedEp(ep.episode_number)}
                          onMouseLeave={() => setHoveredWatchedEp(null)}
                        >
                          {hoveredWatchedEp === ep.episode_number ? (
                            <>
                              <Link to={`/watch/${ep.id}`} className="w-7 h-7 flex items-center justify-center bg-white rounded-full hover:bg-white/80 text-black transition">
                                <Play size={14} fill="currentColor" />
                              </Link>
                              <HelpCircle size={12} className="absolute -top-1 -right-1 text-lunima-gold" />
                            </>
                          ) : (
                            <Check size={16} className="text-green-500" />
                          )}
                        </div>
                      ) : (
                        <Link to={`/watch/${ep.id}`} className="w-9 h-9 flex items-center justify-center border border-white/20 rounded-full hover:bg-white hover:text-black text-white transition">
                          <Play size={16} fill="currentColor" />
                        </Link>
                      )}
                      <button onClick={() => canDownload && handleSingleDownload(ep)} disabled={!canDownload || state === 'downloading'} className={`w-9 h-9 flex items-center justify-center border rounded-full transition disabled:opacity-40 ${canDownload ? "border-white/20 hover:bg-lunima-gold hover:text-black text-white" : "border-white/10 text-white/30 cursor-not-allowed"}`}>
                        {state === 'downloading' ? <Loader2 size={16} className="animate-spin" /> : state === 'complete' ? <Check size={16} className="text-green-500" /> : <Download size={16} />}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {episodes.length === 0 && !loading && (
          <div className="text-lunima-gray text-sm border border-dashed border-white/10 rounded-lg p-8 text-center">
            Nenhum episódio disponível. Execute a sincronização para carregar os episódios.
          </div>
        )}
      </div>
    </main>
  );
}
