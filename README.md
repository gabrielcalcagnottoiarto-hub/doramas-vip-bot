# Bot VIP para Telegram

Bot de Telegram com sistema VIP, catalogo de videos por categorias, pagamentos automaticos (PIX via Mercado Pago e Toncoin), sistema de referencia/convites e painel administrativo completo.

## Funcionalidades

- **Sistema VIP** com trial gratuito de 3 dias para novos usuarios
- **Catalogo dinamico** de videos organizado por categorias (HD para VIP, SD para free)
- **Upload de videos** direto pelo Telegram ou por URL
- **Compressao automatica** de video com ffmpeg (HD 720p / SD 480p)
- **Pagamento PIX automatico** via Mercado Pago (gera QR Code, confirma automaticamente)
- **Pagamento TON automatico** via Tonkeeper (verifica blockchain)
- **PIX manual** como fallback
- **Sistema de referencia** — convide amigos e ganhe acesso gratuito
- **Broadcast** — envie mensagens para todos os usuarios
- **Busca de videos** via Pexels API
- **Painel admin** completo com estatisticas
- **Health check server** para deploy no Render/Railway

## Variaveis de Ambiente

| Variavel | Obrigatoria | Descricao |
|---|---|---|
| `BOT_TOKEN` | Sim | Token do bot (BotFather) |
| `ADMIN_ID` | Sim | ID do Telegram do administrador |
| `MP_ACCESS_TOKEN` | Nao | Token do Mercado Pago (para PIX automatico) |
| `TON_ADDRESS` | Nao | Endereco da carteira TON |
| `TONCENTER_KEY` | Nao | API Key do TON Center |
| `PIX_KEY` | Nao | Chave PIX para pagamento manual |
| `PEXELS_API_KEY` | Nao | API Key do Pexels (busca de videos) |
| `WELCOME_IMAGE_URL` | Nao | URL da imagem de boas-vindas |
| `DB_NAME` | Nao | Nome do banco SQLite (padrao: bot.db) |
| `PORT` | Nao | Porta do health check (padrao: 10000) |

## Instalacao

```bash
pip install -r requirements.txt
```

## Execucao

```bash
export BOT_TOKEN="seu_token_aqui"
export ADMIN_ID="seu_id_aqui"
python main.py
```

## Deploy no Render

1. Crie um novo Web Service no Render
2. Conecte este repositorio
3. Configure as variaveis de ambiente (BOT_TOKEN, ADMIN_ID)
4. O Procfile ja esta configurado: `web: python main.py`
5. O health check server roda automaticamente na porta configurada

## Comandos Admin

| Comando | Descricao |
|---|---|
| `/admin` | Painel admin com estatisticas |
| `/upload Titulo \| Cat \| Preco \| sim/nao` | Upload video (responda a um video) |
| `/upload_low <id>` | Upload versao SD (responda a um video) |
| `/add_url Titulo \| Cat \| URL_HD \| URL_SD \| sim/nao` | Adicionar video por URL |
| `/addvip <user_id> [dias]` | Ativar VIP para usuario |
| `/listusers` | Listar usuarios |
| `/listvideos` | Listar videos do catalogo |
| `/delvideo <id>` | Remover video |
| `/listpayments` | Pagamentos pendentes |
| `/broadcast <msg>` | Enviar mensagem para todos |
| `/config` | Configuracoes gerais |
| `/search_videos <termo>` | Buscar videos via Pexels |

## Comandos do Usuario

| Comando | Descricao |
|---|---|
| `/start` | Menu principal |
| Botoes inline | Navegar catalogo, planos VIP, convites, status |

## Estrutura

- `main.py` — Codigo principal do bot
- `requirements.txt` — Dependencias Python
- `Procfile` — Configuracao para deploy (Render/Railway)
- `runtime.txt` — Versao do Python
- `bot.db` — Banco SQLite (gerado automaticamente)
