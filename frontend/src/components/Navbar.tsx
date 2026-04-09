import { useState, useEffect, useRef } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Search, Bell, X, User, LogOut, ChevronDown } from "lucide-react";
import { searchAnimes, Anime } from "../lib/api";
import { useAuthStore } from "../store/authStore";

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  // Estado da busca
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Anime[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedId, setSelectedId] = useState<number | string | null>(null);
  const searchRef = useRef<HTMLDivElement>(null);

  // Estado do dropdown de perfil
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);

  // Estado do dropdown de notificações
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const notificationsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 50);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Fecha a busca ao clicar fora
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) {
        setSearchResults([]);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Fecha dropdowns ao clicar fora
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setProfileOpen(false);
      }
      if (notificationsRef.current && !notificationsRef.current.contains(event.target as Node)) {
        setNotificationsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Busca com debounce (500ms)
  useEffect(() => {
    if (!searchQuery || searchQuery.trim().length < 2) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const results = await searchAnimes(searchQuery);
        setSearchResults(results);
      } catch (e) {
        console.error(e);
      } finally {
        setIsSearching(false);
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const toggleSearch = () => {
    setIsSearchOpen(!isSearchOpen);
    if (isSearchOpen) {
      setSearchQuery("");
      setSearchResults([]);
      setSelectedId(null);
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery)}`);
      setSearchResults([]);
    }
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const isActive = (path: string) =>
    location.pathname === path
      ? "text-white font-bold"
      : "text-lunima-light-gray hover:text-white transition";

  const userInitial = user?.nome?.charAt(0).toUpperCase() ?? "?";

  return (
    <nav
      className={`fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 lg:px-12 py-3 transition-all duration-500 ${
        scrolled
          ? "bg-lunima-black/95 backdrop-blur-md shadow-lg"
          : "bg-gradient-to-b from-black/80 to-transparent"
      }`}
    >
      <div className="flex items-center gap-8">
        <Link
          to="/home"
          className="text-lunima-gold font-extrabold text-2xl tracking-tight select-none drop-shadow-[0_0_12px_rgba(255,215,0,0.8)]"
        >
          LuminaCast
        </Link>
        <div className="hidden md:flex items-center gap-6 text-sm font-medium">
          <Link to="/home" className={isActive("/home")}>Início</Link>
          <Link to="/animes" className={isActive("/animes")}>Animes</Link>
          <Link to="/desenhos" className={isActive("/desenhos")}>Desenhos</Link>
          <Link to="/minha-lista" className={isActive("/minha-lista")}>Minha Lista</Link>
        </div>
      </div>

      <div className="flex items-center gap-5 text-lunima-light-gray relative">
        {/* ─── Search ─── */}
        <div ref={searchRef} className="flex items-center relative gap-2">
          {!isSearchOpen && (
            <button
              onClick={toggleSearch}
              className="text-lunima-light-gray hover:text-white transition group focus:outline-none"
              aria-label="Pesquisar"
            >
              <Search size={22} className="group-hover:scale-110 transition-transform" />
            </button>
          )}

          <form
            onSubmit={handleSearchSubmit}
            className={`flex items-center transition-all duration-300 overflow-hidden ${
              isSearchOpen
                ? "w-64 bg-black/60 border border-gray-600 rounded px-3 py-1.5"
                : "w-0 border-0 px-0"
            }`}
          >
            {isSearchOpen && (
              <>
                <Search size={18} className="text-gray-400 mr-2 flex-shrink-0" />
                <input
                  type="text"
                  placeholder="Títulos..."
                  className="bg-transparent border-none outline-none text-white text-sm w-full placeholder-gray-400"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  autoFocus
                />
                <button
                  type="button"
                  onClick={toggleSearch}
                  className="ml-2 text-gray-400 hover:text-white flex-shrink-0"
                >
                  <X size={16} />
                </button>
              </>
            )}
          </form>

          {/* Search Dropdown */}
          {isSearchOpen && searchQuery.trim().length >= 2 && (
            <div className="absolute top-full right-0 mt-2 w-72 bg-[#141414] border border-gray-800 shadow-xl rounded py-2 z-50">
              {isSearching && (
                <div className="px-4 py-3 text-sm text-gray-400 text-center">Buscando...</div>
              )}
              {!isSearching && searchResults.length === 0 && (
                <div className="px-4 py-3 text-sm text-gray-400 text-center">Nenhum resultado encontrado</div>
              )}
              {!isSearching &&
                searchResults.map((anime) => (
                  <Link
                    key={anime.id}
                    to={`/media/${anime.id}`}
                    onClick={() => {
                      setSelectedId(anime.id);
                      setSearchResults([]);
                      setSearchQuery("");
                      setIsSearchOpen(false);
                    }}
                    className={`flex items-center gap-3 px-4 py-2 transition ${
                      selectedId === anime.id 
                        ? "bg-lunima-gold/20 cursor-wait" 
                        : "hover:bg-gray-800"
                    }`}
                  >
                    <img
                      src={anime.poster_url || anime.cover_image || ""}
                      alt={anime.title}
                      className="w-10 h-14 object-cover rounded"
                    />
                    <div className="flex flex-col">
                      <span className="text-white text-sm font-medium line-clamp-1">{anime.title}</span>
                      <span className="text-gray-400 text-xs">
                        {anime.year} • {
                          anime.media_type === "anime" ? "Anime" : 
                          anime.media_type === "movie" || anime.media_type === "filme" ? "Filme" : 
                          "Série"
                        }
                      </span>
                    </div>
                  </Link>
                ))}
              {!isSearching && searchResults.length > 0 && (
                <Link
                  to={`/search?q=${encodeURIComponent(searchQuery)}`}
                  onClick={() => setSearchResults([])}
                  className="block w-full text-center py-2 mt-2 border-t border-gray-800 text-lunima-gold text-sm hover:text-white transition"
                >
                  Ver todos os resultados
                </Link>
              )}
            </div>
          )}
        </div>

        {/* ─── Notifications ─── */}
        <div ref={notificationsRef} className="relative">
          <button 
            onClick={() => setNotificationsOpen((n) => !n)}
            className="hover:text-white transition relative" 
            aria-label="Notificações"
          >
            <Bell size={20} />
          </button>
          
          {notificationsOpen && (
            <div className="absolute right-0 top-full mt-2 w-56 bg-zinc-800 border border-zinc-700 rounded-lg shadow-2xl z-50 overflow-hidden animate-fade-in">
              <div className="px-4 py-4 text-center text-lunima-light-gray text-sm">
                Nada aqui no momento
              </div>
            </div>
          )}
        </div>

        {/* ─── Profile Dropdown ─── */}
        <div ref={profileRef} className="relative">
          <button
            onClick={() => setProfileOpen((p) => !p)}
            className="flex items-center gap-1.5 group focus:outline-none"
            aria-label="Perfil"
          >
            <div className="w-8 h-8 rounded bg-gradient-to-br from-lunima-gold to-yellow-600 flex items-center justify-center text-sm font-bold text-black select-none group-hover:ring-2 group-hover:ring-lunima-gold/50 transition">
              {userInitial}
            </div>
            <ChevronDown
              size={14}
              className={`text-lunima-light-gray transition-transform duration-200 ${profileOpen ? "rotate-180" : ""}`}
            />
          </button>

          {profileOpen && (
            <div className="absolute right-0 top-full mt-2 w-44 bg-zinc-800 border border-zinc-700 rounded-lg shadow-2xl z-50 overflow-hidden animate-fade-in">
              {/* User info */}
              <div className="px-3 py-2.5 border-b border-zinc-700">
                <p className="text-white text-sm font-semibold truncate">{user?.nome ?? "Usuário"}</p>
                <p className="text-zinc-400 text-xs truncate">{user?.email}</p>
              </div>

              <Link
                to="/profile"
                onClick={() => setProfileOpen(false)}
                className="flex items-center gap-2.5 px-3 py-2.5 text-sm text-zinc-200 hover:bg-zinc-700 transition"
              >
                <User size={15} /> Perfil
              </Link>

              <button
                onClick={handleLogout}
                className="w-full flex items-center gap-2.5 px-3 py-2.5 text-sm text-red-400 hover:bg-zinc-700 transition"
              >
                <LogOut size={15} /> Sair
              </button>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
}
