def get_embed_urls(media_type: str, tmdb_id: str, season: int = 0, episode: int = 0, slug: str = None, *args, **kwargs) -> list[str]:
    """
    Retorna uma lista de URLs de provedores de embed baseados no TMDB ID.
    Focado em conteúdos que não são Animes (Séries e Desenhos Ocidentais).
    """
    is_series = season > 0 and episode > 0
    
    if is_series:
        providers = [
            # WarezCDN
            f"https://warezcdn.site/serie/{tmdb_id}/{season}/{episode}",
            f"https://warezcdn.site/anime/{tmdb_id}/{season}/{episode}",
            # SuperFlix
            f"https://superflixapi.rest/serie/{tmdb_id}/{season}/{episode}",
            f"https://superflixapi.rest/anime/{tmdb_id}/{season}/{episode}",
            # Vidsrc
            f"https://vidsrc.me/embed/tv?tmdb={tmdb_id}&season={season}&episode={episode}",
        ]
    else:
        # Movies
        providers = [
            f"https://superflixapi.rest/filme/{tmdb_id}",
            f"https://warezcdn.site/filme/{tmdb_id}",
            f"https://vidsrc.me/embed/movie?tmdb={tmdb_id}",
        ]
    
    return providers
