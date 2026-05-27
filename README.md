# 🎬 Novelas Play Bot

Bot do Telegram para assistir novelas turcas e mexicanas com sistema de recompensas.

## Funcionalidades

### Para Usuários
- 🇹🇷 **Novelas Turcas** — Hercai, Emanet, Love is in the Air, e mais
- 🇲🇽 **Novelas Mexicanas** — Rebelde, Teresa, La Usurpadora, e mais
- 🔍 **Busca por nome** — Encontre sua novela favorita rapidamente
- 📺 **Episódios organizados** — Navegue por temporadas e episódios
- 💰 **Sistema de Pontos** — Ganhe pontos assistindo episódios
- 🎁 **Recompensas** — Troque pontos por dias VIP grátis
- 🔥 **Streak diário** — Bônus por assistir todos os dias
- 🔗 **Convide amigos** — Ganhe pontos extras por cada amigo

### Planos
| Plano | Gratuito | VIP |
|-------|----------|-----|
| Anúncios | Com anúncios a cada 2 eps | Sem anúncios |
| Qualidade | SD | Full HD |
| Preço | Grátis | A partir de R$9.90/semana |

### Para Admin
- `/addlink <novela_id> <ep> <link>` — Adicionar link de episódio
- `/addlinks <novela_id> <ep_inicio> <links...>` — Adicionar vários links
- `/darvip <user_id> <dias>` — Ativar VIP para um usuário
- `/stats` — Ver estatísticas do bot
- `/broadcast <msg>` — Enviar mensagem para todos

## Configuração

### Variáveis de Ambiente
```
BOT_TOKEN=seu_token_do_botfather
ADMIN_ID=seu_telegram_user_id
MP_ACCESS_TOKEN=token_mercado_pago (opcional)
```

### Deploy no Render
1. Crie um novo Web Service no Render
2. Conecte este repositório
3. Configure as variáveis de ambiente
4. Deploy!

## Como Funciona o Sistema de Pontos

| Ação | Pontos |
|------|--------|
| Assistir episódio | +10 |
| Ver anúncio | +5 |
| Bônus diário (1º ep do dia) | +20 |
| Convidar amigo | +50 |
| Streak 3+ dias | +5 extra |
| Streak 7+ dias | +15 extra |

### Recompensas
| Pontos | Recompensa |
|--------|-----------|
| 100 | 1 dia VIP |
| 300 | 3 dias VIP |
| 500 | 7 dias VIP |
| 1000 | 30 dias VIP |
| 2500 | VIP Vitalício |

## Estrutura do Projeto
```
├── bot.py              # Bot principal
├── data/               # Dados (gerado automaticamente)
│   ├── users.json      # Dados dos usuários
│   ├── novelas.json    # Links dos episódios
│   └── watch_history.json
├── requirements.txt    # Dependências
├── Procfile           # Config de deploy
└── runtime.txt        # Versão do Python
```

## Tecnologias
- Python 3.11
- python-telegram-bot 22.7
- Render (deploy)
