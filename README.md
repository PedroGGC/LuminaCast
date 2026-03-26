# Feature: Histórico de "Continuar Assistindo" e Rastreador de Episódios

Precisamos implementar um sistema de rastreamento de histórico para criar uma fileira "Continuar Assistindo" (limite de 20 mídias recentes) e marcar visualmente os episódios já assistidos na interface. Como lidamos com Iframes, faremos um "Soft Tracking" (marcar como assistido ao acessar a rota do player).

**1. Backend - Banco de Dados (`app/models.py`):**
* Crie uma tabela `WatchHistory` contendo:
  * `id` (Primary Key)
  * `media_id` (String ou Integer, ex: "mal_59978" ou TMDB ID)
  * `media_type` (String: "anime", "movie", "tv")
  * `last_episode` (Integer, o último episódio acessado)
  * `watched_episodes` (JSON ou String contendo uma lista de episódios já vistos)
  * `updated_at` (DateTime, atualizado a cada novo acesso)

**2. Backend - Lógica de Fila e Rotas da API (`app/routes/history.py` ou similar):**
* **POST `/api/history`:** Recebe `media_id`, `media_type` e `episode_number`.
  * Lógica de Upsert: Se a mídia já existe no histórico, atualize o `last_episode` e adicione o `episode_number` na lista `watched_episodes` (sem duplicar). Atualize o `updated_at`.
  * Se não existe, crie.
  * Lógica de Limite (Garbage Collector): Após inserir/atualizar, conte quantos registros existem. Se houver mais de 20, delete os mais antigos (ordenados por `updated_at` ASC) para manter exatamente 20.
* **GET `/api/history`:** Retorna a lista das 20 mídias do histórico ordenadas por `updated_at` DESC. (Deve retornar dados suficientes para o frontend montar os cards: ID, tipo, título, poster, último episódio).
* **GET `/api/history/{media_id}`:** Retorna apenas a lista `watched_episodes` daquela mídia específica para o frontend saber quais botões pintar de "assistido".

**3. Frontend - Integração (Instruções/Código):**
* Implemente a chamada para o `POST /api/history` no evento `useEffect` da página do Player de Vídeo (assim que o componente montar).
* Na Home, consuma o `GET /api/history` e renderize um novo carrossel "Continuar Assistindo" no TOPO da página (acima dos Lançamentos). O card deve mostrar "Episódio X" como subtítulo.
* Na página de detalhes da mídia (onde fica a lista de episódios), faça um `GET /api/history/{media_id}`. Ao renderizar os botões/links dos episódios, verifique se o número do episódio está na lista. Se sim, aplique uma classe CSS visual de "assistido" (ex: opacidade reduzida).

Crie os arquivos backend necessários e me forneça os snippets do frontend para eu aplicar.