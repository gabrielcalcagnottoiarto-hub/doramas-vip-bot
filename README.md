# 💎 GRUPO VIP DA PELADA - BOT TELEGRAM 💎

Bot Telegram para **@GrupoVipdaPeladaBOT** com sistema FREE + VIP, compressão ffmpeg, pagamento PIX/TON.

## 🚀 Funcionalidades
- **Sistema FREE + VIP**: Grátis (SD 480p + propagandas) vs VIP (HD 720p, sem ads, mais conteúdo)
- **Compressão ffmpeg**: Vídeos comprimidos automaticamente antes de enviar (480p ou 720p)
- **Pagamento PIX e TON/Tonkeeper**: Menus de pagamento integrados
- **Catálogo por categorias**: Navegação com botões inline
- **APIs integradas**: Pexels (vídeos) e TMDB (filmes/séries)
- **Gerenciador de arquivos**: Listar, mover, copiar, deletar vídeos no servidor
- **Health check HTTP**: Para deploy 24/7 no Render/Railway
- **SQLite**: Banco de dados persistente para usuários, vídeos e config

## 🛠️ Como Ligar
1. Instale ffmpeg: `sudo apt-get install -y ffmpeg`
2. Instale dependências: `pip install -r requirements.txt`
3. Configure `TOKEN` e `ADMIN_ID` no `main.py` (ou variáveis de ambiente)
4. Execute: `python main.py`

## 🌐 Deploy 24/7 no Render
1. Faça merge do PR e vá em https://render.com → New Web Service
2. Conecte o repo `doramas-vip-bot`
3. **Build command:** `apt-get update && apt-get install -y ffmpeg && pip install -r requirements.txt`
4. **Start command:** `python main.py`
5. A variável `PORT` é fornecida automaticamente pelo Render

## 👑 Comandos de Admin
| Comando | Descrição |
|---|---|
| `/upload Titulo \| Categoria \| Preço \| sim/nao` | Postar vídeo (responder a um vídeo) |
| `/upload_low <id>` | Adicionar versão SD (responder a vídeo SD) |
| `/add_url Titulo \| Categoria \| URL_HD \| URL_SD \| sim/nao` | Adicionar vídeo por URL |
| `/config pix <chave>` | Mudar chave PIX |
| `/config ad <texto>` | Configurar propaganda |
| `/config vip <user_id> sim/nao` | Dar/remover VIP |
| `/config broadcast <msg>` | Mensagem para todos |
| `/config pexels <key>` | Configurar API Pexels |
| `/config tmdb <key>` | Configurar API TMDB |
| `/listusers` | Listar usuários |
| `/manage_files list/move/copy/delete/info` | Gerenciar arquivos no servidor |

## 🎮 Comandos de Usuário
| Comando | Descrição |
|---|---|
| `/start` | Menu principal |
| `/send_content` | Conteúdo aleatório |
| `/search_videos <termo>` | Buscar vídeos (Pexels API) |
| `/search_api <termo>` | Buscar filmes/séries (TMDB API) |
