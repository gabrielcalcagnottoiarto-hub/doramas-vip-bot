# DoramaAI Bot — Completo (GitHub + Render)

## Variáveis de ambiente

Configurar no Render Dashboard > Environment:

```
TELEGRAM_BOT_TOKEN   = token do @BotFather (obrigatório)
FISH_AUDIO_API_KEY   = chave da API Fish.audio (TTS primário — obrigatório)
ELEVENLABS_API_KEY   = chave da API ElevenLabs (TTS fallback — opcional)
DID_API_KEY          = chave da API D-ID (para vídeos animados)
TELEGRAM_ADMIN_ID    = seu ID no Telegram (para comandos admin)
OPENPIX_API_KEY      = chave OpenPix (PIX automático — opcional)
PIX_KEY              = chave PIX manual (opcional)
TONCOIN_ADDRESS      = endereço TON (opcional)
VIP_PRICE_BRL        = preço VIP em reais (padrão: 29.90)
```

Veja `.env.example` para lista completa (incluindo vozes customizadas).

## Deploy no Render (via GitHub)

1. Crie um repositório no GitHub e faça push deste código
2. No [Render Dashboard](https://dashboard.render.com/), clique **New > Web Service**
3. Conecte seu repositório GitHub
4. Render detecta o `Dockerfile` automaticamente
5. Configure as variáveis de ambiente no painel
6. Clique **Deploy**

Ou use o Blueprint (render.yaml):
- Edite `render.yaml` e substitua a URL do repo
- No Render, vá em **Blueprints > New Blueprint Instance**
- Aponte para o repositório

## Webhook PIX automático

Após deploy, configure no painel OpenPix:
```
URL: https://SEU_DOMINIO.onrender.com/api/webhooks/pix
Evento: OPENPIX:CHARGE_COMPLETED
```

## Comandos admin no Telegram

```
/setvip <id> true|false  — ativar/desativar VIP
/broadcast <mensagem>    — enviar para todos
/setpix <chave>          — atualizar chave PIX
/settoncoin <endereço>   — atualizar TON
/stats                   — ver estatísticas
/adminhelp               — lista de comandos
```

## Build local

```bash
pnpm install && pnpm --filter @workspace/api-server run build
node --enable-source-maps artifacts/api-server/dist/index.mjs
```

## Fish Audio — Configuração de vozes

O bot usa Fish.audio como TTS principal. As vozes podem ser customizadas
via variáveis de ambiente (ex: `FISH_VOICE_KO=<reference_id>`).

Para explorar vozes disponíveis: https://fish.audio/discovery
