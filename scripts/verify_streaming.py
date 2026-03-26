import sys
import os

# Add backend directory to sys.path
backend_path = os.path.join(os.getcwd(), "backend")
sys.path.append(backend_path)

def test_embed_urls():
    print("Iniciando teste de geracao de URLs de Embed...")
    
    # Importa a funcao diretamente
    try:
        from app.services.embed_providers import get_embed_urls
    except ImportError as e:
        print(f"Erro ao importar: {e}")
        # Tenta importar sem o prefixo 'app' se necessario
        try:
            sys.path.append(os.path.join(backend_path, "app"))
            from services.embed_providers import get_embed_urls
        except ImportError:
            print("Nao foi possivel importar o servico.")
            return

    tmdb_id = "12345"
    season = 1
    episode = 5
    
    print(f"Testando para ID {tmdb_id}, T{season} E{episode}")
    urls = get_embed_urls(tmdb_id, season, episode)
    
    print("URLs geradas:")
    for url in urls:
        print(f" - {url}")
        
    # Validacoes basicas
    assert len(urls) == 5, "Deveria retornar 5 provedores"
    assert "warezcdn.site/serie" in urls[0]
    assert "superflixapi.rest/serie" in urls[1]
    assert "warezcdn.site/anime" in urls[2]
    assert "superflixapi.rest/anime" in urls[3]
    assert "vidsrc.me" in urls[4]
    
    print("\n[OK] Teste de geracao de URLs concluido com sucesso!")

if __name__ == "__main__":
    test_embed_urls()
