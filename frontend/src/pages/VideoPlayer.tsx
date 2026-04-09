import { useEffect, useRef, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Play, Pause, Maximize, Volume2, SkipForward } from "lucide-react";
import Hls from "hls.js";
import { api } from "../lib/api";

interface StreamData {
  stream_url: string;
  embed_urls: string[];
  media_id: string;
  media_type?: string;
  title: string | null;
  season_number: number;
  episode_number: number;
  is_iframe?: boolean;
  next_episode?: {
    id: number;
    number: number;
    title: string;
  };
}

export default function VideoPlayer() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [stream, setStream] = useState<StreamData | null>(null);
  const [activeUrl, setActiveUrl] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedServerIndex, setSelectedServerIndex] = useState<number>(0);
  
  // Estados customizados do Player
  const [isPlaying, setIsPlaying] = useState(true);
  const [progress, setProgress] = useState(0);
  const [bufferedProgress, setBufferedProgress] = useState(0);
  const [currentTimeText, setCurrentTimeText] = useState("00:00");
  const [durationText, setDurationText] = useState("00:00");
  const [showNextPopup, setShowNextPopup] = useState(false);

  // ... (Mantém os refs existentes e formatTime) ...
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const hlsRef = useRef<Hls | null>(null);

  // Helper: Formata o tempo
  const formatTime = (seconds: number) => {
    if (isNaN(seconds)) return "00:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
  };

  // ... (Lógica de fetch de stream permanece a mesma) ...
  useEffect(() => {
    if (!id) return;
    setLoading(true);
    api
      .get(`/api/stream/${id}`)
      .then((res) => {
        const data = res.data;
        setStream(data);
        
        if (data.stream_url) {
          setActiveUrl(data.stream_url);
        } else if (data.embed_urls && data.embed_urls.length > 0) {
          setActiveUrl(data.embed_urls[0]);
          setSelectedServerIndex(0);
        }

        // Registra no histórico
        const mediaId = String(data.media_id);
        const mediaType = data.media_type || 'anime';
        const episodeNumber = data.episode_number;
        
        if (mediaId && episodeNumber) {
          api.post('/api/history', null, {
            params: { media_id: mediaId, media_type: mediaType, episode_number: episodeNumber }
          }).catch(console.error);
        }
      })
      .catch((e) => setError(e.response?.data?.detail ?? e.message))
      .finally(() => setLoading(false));
  }, [id]);

  // Handler: mudança de servidor para conteúdo Western
  const handleServerChange = (url: string, index: number) => {
    setActiveUrl(url);
    setSelectedServerIndex(index);
    setIsPlaying(true);
  };

  // Lógica: Controle de Tempo, Detecção do Próximo Episódio e Buffer
  const handleTimeUpdate = () => {
    const video = videoRef.current;
    if (!video) return;

    const current = video.currentTime;
    const duration = video.duration;
    
    if (duration > 0) {
      setProgress((current / duration) * 100);
      setCurrentTimeText(formatTime(current));
      setDurationText(formatTime(duration));

      // Lógica do Buffer
      const buffered = video.buffered;
      if (buffered.length > 0) {
        setBufferedProgress((buffered.end(buffered.length - 1) / duration) * 100);
      }

      // Mostra popup aos 90% do vídeo
      if (current / duration > 0.9) {
        setShowNextPopup(true);
      } else {
        setShowNextPopup(false);
      }
    }
  };

  // Lógica: Play/Pause
  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  // Lógica: Tela Cheia
  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().catch((err) => {
        console.error(`Error attempting to enable full-screen mode: ${err.message}`);
      });
    } else {
      document.exitFullscreen();
    }
  };

  // Handler: Seek (Progress Bar)
  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const video = videoRef.current;
    if (!video) return;
    const time = (Number(e.target.value) / 100) * video.duration;
    video.currentTime = time;
    setProgress(Number(e.target.value));
  };

  // Initialize HLS
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !stream || !activeUrl) return;

    const isDirectVideo = activeUrl.includes(".mp4") || activeUrl.includes(".m3u8");
    if (!isDirectVideo) return;

    if (hlsRef.current) {
      hlsRef.current.destroy();
      hlsRef.current = null;
    }

    const isHls = activeUrl.includes(".m3u8");

    if (isHls && Hls.isSupported()) {
      const hls = new Hls({ enableWorker: true });
      hls.loadSource(activeUrl);
      hls.attachMedia(video);
      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        video.play().catch(() => {});
        setIsPlaying(true);
      });
      hlsRef.current = hls;
    } else {
      video.src = activeUrl;
      video.play().catch(() => {});
      setIsPlaying(true);
    }

    return () => {
      if (hlsRef.current) {
        hlsRef.current.destroy();
        hlsRef.current = null;
      }
    };
  }, [activeUrl, stream]);

  if (loading) {
    return (
      <div className="h-screen w-full bg-black flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-lunima-gold border-t-transparent rounded-full animate-spin" />
          <p className="text-zinc-400 text-sm font-outfit">Carregando stream...</p>
        </div>
      </div>
    );
  }

  if (error || !stream) {
    return (
      <div className="h-screen w-full bg-black flex items-center justify-center">
        <div className="text-center space-y-4">
          <p className="text-lunima-gold text-xl font-bold font-outfit">Erro no Player</p>
          <p className="text-white text-sm max-w-md font-outfit">{error ?? "Vídeo não encontrado"}</p>
          <button
            onClick={() => navigate(-1)}
            className="inline-flex items-center gap-2 mt-4 px-6 py-2 bg-lunima-gold hover:bg-lunima-gold-hover rounded text-sm font-semibold transition font-outfit text-black"
          >
            <ArrowLeft size={16} /> Voltar
          </button>
        </div>
      </div>
    );
  }

  const isEmbed = !activeUrl.includes(".mp4") && !activeUrl.includes(".m3u8");

  // === INÍCIO DO DEBUG (Logs de Desenvolvimento) ===
  console.log("=== DEBUG DO PLAYER ===");
  console.log("1. Objeto Stream Completo:", stream);
  console.log("2. URL Ativa (activeUrl):", activeUrl);
  console.log("3. Caiu no Iframe? (isEmbed):", isEmbed);
  console.log("=======================");
  // === FIM DO DEBUG ===

  return (
    <div ref={containerRef} className="h-screen w-full bg-black relative flex flex-col items-center justify-center overflow-hidden">
      {/* Back button */}
      <button
        onClick={() => {
          if (stream?.media_id) {
            navigate(`/media/${stream.media_id}`);
          } else {
            navigate(-1);
          }
        }}
        className="absolute top-[20px] left-[20px] z-50 flex items-center gap-3 px-6 py-3 bg-black/70 backdrop-blur-xl text-white border border-white/20 rounded-xl hover:text-lunima-gold hover:bg-black/90 transition-all duration-300 shadow-2xl group/btn"
      >
        <ArrowLeft size={24} className="group-hover/btn:-translate-x-1 transition-transform" />
        <span className="font-bold text-base select-none font-outfit">Voltar</span>
      </button>

      {isEmbed ? (
        <div className="w-full h-full flex flex-col items-center justify-center">
          <div className="relative w-full flex-grow flex items-center justify-center bg-black overflow-hidden">
            <div className="relative w-full aspect-video max-h-full">
              <iframe
                key={activeUrl}
                src={activeUrl}
                className="absolute inset-0 w-full h-full border-none z-0"
                allow="autoplay; encrypted-media; picture-in-picture"
                allowFullScreen
              ></iframe>
            </div>
          </div>
          
          {stream.embed_urls && stream.embed_urls.length > 1 && (
            <div className="bg-zinc-900/90 p-4 flex flex-wrap items-center justify-center gap-3 border-t border-white/10 w-full z-20">
              <span className="text-zinc-400 text-xs font-bold uppercase tracking-wider mr-2 font-outfit">Servidores:</span>
              {stream.embed_urls.map((url, idx) => (
                <button
                  key={idx}
                  onClick={() => handleServerChange(url, idx)}
                  className={`px-4 py-1.5 rounded-md text-xs font-semibold transition-all font-outfit ${
                    selectedServerIndex === idx 
                    ? "bg-lunima-gold text-black shadow-[0_0_15px_rgba(234,179,8,0.3)]" 
                    : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700 hover:text-white"
                  }`}
                >
                  Opção {idx + 1}
                </button>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="relative w-full h-full flex items-center justify-center group overflow-hidden">
          <video
            ref={videoRef}
            src={activeUrl}
            autoPlay
            playsInline
            onTimeUpdate={handleTimeUpdate}
            onClick={togglePlay}
            className="w-full h-full cursor-pointer object-contain"
          />

          {/* Custom Controls Bar */}
          <div className="absolute bottom-0 left-0 w-full bg-gradient-to-t from-black to-transparent pt-20 pb-8 px-6 opacity-0 group-hover:opacity-100 transition-all duration-300 z-10 translate-y-2 group-hover:translate-y-0">
            {/* Progress Bar Container (Barra VIP com 3 Camadas) */}
            <div className="relative w-full mb-6 group/progress">
              <input
                type="range"
                min="0"
                max="100"
                value={progress}
                onChange={handleSeek}
                className="absolute inset-0 w-full h-1 bg-transparent cursor-pointer opacity-0 z-20"
              />
              <div className="w-full h-1.5 bg-zinc-700 rounded-full overflow-hidden backdrop-blur-sm relative">
                {/* 1. Preview de Carregamento (Buffer) */}
                <div 
                  className="absolute top-0 left-0 h-full bg-white/30 transition-all duration-300"
                  style={{ width: `${bufferedProgress}%` }}
                />
                {/* 2. Progresso Atual */}
                <div 
                  className="absolute top-0 left-0 h-full bg-lunima-gold shadow-[0_0_10px_rgba(234,179,8,0.5)] transition-all duration-100"
                  style={{ width: `${progress}%` }}
                >
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 w-4 h-4 bg-lunima-gold rounded-full scale-0 group-hover/progress:scale-100 transition-transform" />
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-6">
                <button 
                  onClick={togglePlay}
                  className="text-white hover:text-lunima-gold transition-colors filter drop-shadow-lg"
                >
                  {isPlaying ? <Pause size={32} fill="currentColor" /> : <Play size={32} fill="currentColor" />}
                </button>

                <div className="flex items-center gap-4">
                  <Volume2 size={24} className="text-zinc-400" />
                  <div className="text-white font-outfit font-medium text-lg">
                    <span className="text-lunima-gold">{currentTimeText}</span>
                    <span className="text-zinc-500 mx-2">/</span>
                    <span className="text-zinc-400">{durationText}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-6">
                <div className="text-right hidden sm:block">
                  <p className="text-white font-bold text-sm font-outfit uppercase tracking-wider">{stream.title}</p>
                  <p className="text-zinc-400 text-xs font-medium font-outfit">S{stream.season_number} E{stream.episode_number}</p>
                </div>
                <button 
                  onClick={toggleFullscreen}
                  className="text-white hover:text-lunima-gold transition-colors"
                >
                  <Maximize size={28} />
                </button>
              </div>
            </div>
          </div>

          {/* Next Episode Popup */}
          {(showNextPopup && stream.next_episode) && (
            <div 
              onClick={() => navigate(`/player/${stream.next_episode?.id}`)}
              className="absolute bottom-32 right-8 z-20 bg-black/80 backdrop-blur-xl border border-white/10 p-6 rounded-2xl cursor-pointer hover:bg-black transition-all duration-500 animate-in slide-in-from-right fade-in group/next shadow-2xl hover:scale-105"
            >
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-lunima-gold/20 rounded-full flex items-center justify-center text-lunima-gold">
                  <SkipForward size={24} />
                </div>
                <div className="flex flex-col">
                  <span className="text-lunima-gold font-bold text-xs uppercase tracking-widest mb-1">Próximo Episódio</span>
                  <span className="text-white font-outfit font-medium text-lg max-w-[200px] truncate">
                    E{stream.next_episode.number} - {stream.next_episode.title}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
