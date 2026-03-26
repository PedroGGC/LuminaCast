  <h1>LuminaCast — Streaming Aggregator</h1>
  <p><strong>A robust, dual-source streaming aggregator for Animes and Cartoons with a Just-In-Time (JIT) Sync Architecture.</strong></p>
</div>

<br />

## Visão Geral

> **Desenvolvimento Expresso:** Este projeto educacional foi concebido e estabelecido do zero em tempo recorde, tendo iniciado na noite de **sexta-feira, 20 de março de 2026**. Com o apoio de Inteligência Artificial, toda a arquitetura base, scraper de vídeos e a refatoração completa ("Pente Fino") foram entregues em apenas 5 dias de ciclo de engenharia ativa.

**LuminaCast** é um agregador de streaming de mídia com arquitetura "Lazy-Loaded". Ao invés de manter um banco de dados gigantesco com todo o conteúdo existente, o sistema nasce vazio e é populado sob demanda **(Just-In-Time Sync)** de forma assíncrona.

O projeto divide estritamente o conteúdo em duas verticais independentes:

- **Animes:** Controlados 100% pela API **Jikan (MyAnimeList)** para manter fidelidade na ordem de temporadas e evitar a bagunça estrutural do TMDB com obras japonesas. A extração de streams é feita principalmente através de um provedor de streaming (incluindo tratamento de embeds e scrapers do Blogger/Google Video).
- **Desenhos Ocidentais:** Controlados 100% pela API **TMDB**, com filtros pesados de Regex e análise de origem (`origin_country == "JP"`, `original_language == "ja"`) para garantir que os animes não poluam a área ocidental do sistema.

## Tecnologias

### Backend (Python)

- **Framework:** FastAPI (totalmente assíncrono).
- **ORM & Banco:** SQLAlchemy com banco local SQLite (`/data/luminacast.db`).
- **HTTP Client:** `httpx.AsyncClient` com pool de conexões (sessões globais reutilizadas para máxima performance).
- **Utilitários:** `BeautifulSoup4` para scraping, Regex compilados otimizados.

### Frontend (React)

- **Framework:** React 18 + Vite + TypeScript.
- **Estilização:** Tailwind CSS v3 com suporte a Glassmorphism (Efeito _Acrylic_).
- **Roteamento:** React Router DOM (Múltiplas views com passagem de estado explícito).
- **Ícones & UI:** Tabler Icons, Headless UI (Zustand para estado global, se aplicável).

---

## Padrões e Regras de Arquitetura (Contexto Core)

1. **Padrão "Just-In-Time (JIT) Sync":**
   O SQLite local atua essencialmente como um cache de longa duração.
   - Quando o usuário entra na `Home`, ele vê dados diretos das APIs externas.
   - Ao apertar para ver detalhes (`/api/media/{id}/full`), o backend intercepta, verifica se já existe no banco e, caso não, engatilha um `Sync Assíncrono`.
   - Apenas então o anime/desenho é mapeado, todos os episódios são pré-calculados/raspados e inseridos no DB.

2. **Tipagem Flexível de IDs Front ↔ Back:**
   Para garantir que o backend direcione a busca para a API correta de forma independente, **todo o envio de IDs a partir do Client possui prefixo**.
   - Animes: `mal_XXXXX`
   - TMDB/Western: `tmdb_XXXXX`

3. **Tratamento Silencioso de Falhas (Graceful Degradation):**
   Se o Scraper encontrar um vídeo quebrado, for barrado no cloudflare, ou o regex falhar, a UI do usuário NUNCA deve quebrar. O backend absorve a falha, loga internamente e injeta dinamicamente o **link de falha seguro** (M3U8 de fallback para placeholder).

4. **Regex pré-compilados:**
   Todas as regras de "Limpeza de Slug" e "DNA Japonês" (ex: `[\u3040-\u30ff\u4e00-\u9fff]`) são compiladas em escopo de módulo ou classe (via `re.compile()`) apenas 1x no startup para evitar gargalo I/O no event loop de extração pesada do parser html.

---

## Instalação e Execução Local

### Pré-requisitos

- Python 3.10+
- Node.js 18+ (recomendado 20.x lts)

### 1. Configurando o Backend

Navegue até a pasta `backend`:

```bash
cd backend
python -m venv venv

# Ative o ambiente virtual
# No Windows:
venv\Scripts\activate
# No Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

Crie um arquivo `.env` na raiz do `backend` com a sua key:

```env
TMDB_API_KEY=sua_chave_do_tmdb_aqui
```

Inicie a aplicação FastAPI:

```bash
uvicorn app.main:app --reload --port 8000
```

> O backend rodará em `http://localhost:8000` e a documentação interativa em `http://localhost:8000/docs`.

### 2. Configurando o Frontend

Navegue até a pasta `frontend`:

```bash
cd frontend
npm install
# ou yarn install / pnpm install

npm run dev
```

> O frontend rodará por padrão em `http://localhost:5173`. O proxy da API já deve estar configurado no `vite.config.ts` apontando para o backend, então as chamadas para `/api/` fluirão tranquilamente.

---

## Funcionalidades (O que tem dentro?)

- **Home Híbrida**: Mix de TMDB e MyAnimeList (Jikan) compilados em carrosséis responsivos e paralelos via `asyncio.gather`.
- **Efeito Acrylic Glassmorphism**: Cards com desfoque nativo imersivo no Header principal.
- **Filtros e Catálogo Paginado**: Seleção dinâmica de categorias via pills sem tocar no banco de forma prematura.
- **Minha Lista Universal**: Você pode favoritar um desenho ou anime e ele salva uniformemente.
- **Auto-Seed Assíncrono VIP**: Opcionalmente roda uma fila `asyncio.sleep` rodando em background importando um setup base sem travar o EventLoop e sem explodir Rate Limit (429 HTTP).

---

## Controle de Qualidade (Changelog Recente)

Recentemente o ecossistema passou por um "**Pente Fino**" (Refatoração pesada). Ganhos da última build:

- Implementado **Connection Pooling** Global via httpx, acabando com starvation de Sockets TCQ.
- Adicionado Filtro "Anti-Anime" com Regex Centralizado para proteger o feed Western (Home's Cartoons Category).
- Extirpação de Dead Code TMDB -> Jikan, garantindo zero-contact no model mapper das rotas de Search.
- Remoção do db `drop_all` do Seed, trazendo banco de dados **100% Persistente via SQLite local**.

---

## ⚠️ Aviso Legal (Disclaimer)

Este projeto tem fins estritamente educacionais e serve como uma Prova de Conceito (_Proof of Concept_) para estudos de arquitetura de software, consumo de APIs RESTful (TMDB/Jikan) e técnicas de Web Scraping.

Este repositório **não hospeda, não armazena e não distribui** nenhum tipo de arquivo de vídeo, imagem ou material protegido por direitos autorais. Todo o conteúdo reproduzido é proveniente de fontes públicas e de terceiros na internet, sendo acessado em tempo real através de links indexados externamente.

O código atua apenas como um cliente de agregação e roteamento. Os desenvolvedores deste projeto não têm afiliação com os provedores de conteúdo e não se responsabilizam pelo mau uso da ferramenta.

---
