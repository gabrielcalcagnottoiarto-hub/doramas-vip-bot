# DORAMAS VIP Bot

Bot de Telegram para acesso VIP a catalogo de doramas, com sistema de assinatura, pagamento automatico (PIX via Mercado Pago e TON via Tonkeeper), trial gratuito e programa de indicacoes.

## Funcionalidades

- **Catalogo de Doramas** com navegacao paginada e episodios
- **Sistema VIP** com planos mensal, trimestral e anual
- **Trial gratuito** de 3 dias para novos usuarios
- **Pagamento automatico PIX** via Mercado Pago com QR Code
- **Pagamento automatico TON** via Tonkeeper com verificacao na blockchain
- **Programa de indicacoes** — convide amigos e ganhe acesso gratuito
- **Video de boas-vindas** com cache automatico de file_id
- **Painel Admin** com estatisticas, gestao de usuarios e broadcast
- **Anuncios** configuraveis para usuarios gratuitos

## Como Configurar

### 1. Variaveis de Ambiente

| Variavel | Descricao | Obrigatoria |
|---|---|---|
| `BOT_TOKEN` | Token do bot do Telegram (via @BotFather) | Sim |
| `ADMIN_ID` | ID numerico do administrador no Telegram | Sim |
| `MP_ACCESS_TOKEN` | Token de acesso do Mercado Pago (para PIX) | Nao |
| `TONCENTER_KEY` | API Key do TON Center (para verificacao TON) | Nao |

### 2. Instalar Dependencias

```bash
pip install -r requirements.txt
```

### 3. Executar

```bash
python bot_final.py
```

Ou com variaveis de ambiente:

```bash
BOT_TOKEN="seu_token" ADMIN_ID="seu_id" python bot_final.py
```

## Comandos

### Usuarios

- `/start` — Menu principal com catalogo, planos VIP e link de convite

### Admin

| Comando | Descricao | Exemplo |
|---|---|---|
| `/admin` | Painel admin com estatisticas | `/admin` |
| `/addlink <chave> <url>` | Adicionar link de episodio | `/addlink d1_1 https://...` |
| `/addvip <user_id> [dias]` | Dar VIP a um usuario | `/addvip 123456 30` |
| `/upload <dorama> <ep> <url>` | Upload de episodio | `/upload d1 3 https://...` |
| `/config <sub> [args]` | Configuracoes dinamicas | Ver abaixo |
| `/broadcast <msg>` | Enviar mensagem para todos | `/broadcast Novidades!` |
| `/listusers` | Listar usuarios cadastrados | `/listusers` |
| `/listpayments` | Ver pagamentos pendentes | `/listpayments` |
| `/setreferrals <n>` | Alterar minimo de indicacoes | `/setreferrals 3` |

### Subcomandos do `/config`

- `/config pix <chave>` — Atualizar chave PIX
- `/config ton <endereco>` — Atualizar endereco TON
- `/config ad <texto>` — Configurar anuncio (vazio para remover)
- `/config vip <user_id> <dias>` — Dar VIP a usuario
- `/config broadcast <mensagem>` — Enviar mensagem em massa

## Estrutura de Arquivos

```
bot_final.py        # Codigo principal do bot
requirements.txt    # Dependencias Python
Procfile            # Deploy (Heroku/Railway)
runtime.txt         # Versao do Python
welcome_video.mp4   # Video de boas-vindas (opcional)
users.json          # Dados de usuarios (gerado automaticamente)
video_links.json    # Links dos episodios (gerado automaticamente)
config.json         # Configuracoes dinamicas (gerado automaticamente)
payments.json       # Pagamentos pendentes (gerado automaticamente)
```

## Deploy

O bot esta configurado para deploy em plataformas como Heroku ou Railway:

- `Procfile` define o processo web
- `runtime.txt` especifica Python 3.11.0
- Variaveis de ambiente devem ser configuradas na plataforma
