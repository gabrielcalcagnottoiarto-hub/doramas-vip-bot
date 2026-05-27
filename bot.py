import os
import json
import logging
import asyncio
import time
import random
from datetime import datetime, timedelta
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────────
TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = os.environ.get("ADMIN_ID", "")
MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN", "")

PLANOS_VIP = {
    "semanal": {"nome": "Semanal", "valor_brl": 9.90, "dias": 7},
    "mensal": {"nome": "Mensal", "valor_brl": 19.90, "dias": 30},
    "trimestral": {"nome": "Trimestral", "valor_brl": 49.90, "dias": 90},
    "anual": {"nome": "Anual", "valor_brl": 149.90, "dias": 365},
}

# Pontos por ação
PONTOS_POR_EPISODIO = 10
PONTOS_POR_ANUNCIO = 5
PONTOS_BONUS_DIARIO = 20
PONTOS_REFERRAL = 50

# Recompensas
RECOMPENSAS = {
    100: "1 dia VIP grátis",
    300: "3 dias VIP grátis",
    500: "7 dias VIP grátis",
    1000: "30 dias VIP grátis",
    2500: "VIP Vitalício",
}

AD_INTERVAL_EPISODES = 2  # A cada 2 episódios mostra anúncio

# ─────────────────────────────────────────────
# CAMINHOS
# ─────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

USERS_FILE = DATA_DIR / "users.json"
NOVELAS_FILE = DATA_DIR / "novelas.json"
WATCH_HISTORY_FILE = DATA_DIR / "watch_history.json"
CONFIG_FILE = DATA_DIR / "config.json"

WELCOME_IMAGE_URL = (
    "https://img.freepik.com/fotos-gratis/conceito-de-colagem-de-novela_23-2150062102.jpg"
)

# ─────────────────────────────────────────────
# CATÁLOGO DE NOVELAS
# ─────────────────────────────────────────────
NOVELAS_CATALOG = {
    # Novelas Turcas
    "t1": {
        "title": "Hercai - Amor e Vingança",
        "category": "turca",
        "episodes": 69,
        "description": "Uma história de amor e vingança nas terras da Mesopotâmia.",
        "year": 2019,
    },
    "t2": {
        "title": "Emanet - Legado",
        "category": "turca",
        "episodes": 100,
        "description": "Seher precisa cuidar do bebê de sua irmã falecida.",
        "year": 2020,
    },
    "t3": {
        "title": "Erkenci Kuş - Pássaro Madrugador",
        "category": "turca",
        "episodes": 51,
        "description": "Sanem sonha em ser escritora e se apaixona pelo seu chefe.",
        "year": 2018,
    },
    "t4": {
        "title": "Kara Sevda - Amor Eterno",
        "category": "turca",
        "episodes": 74,
        "description": "Um amor impossível entre classes sociais diferentes.",
        "year": 2015,
    },
    "t5": {
        "title": "Sen Cal Kapimi - Love is in the Air",
        "category": "turca",
        "episodes": 52,
        "description": "Eda finge ser noiva de Serkan para conseguir uma bolsa.",
        "year": 2020,
    },
    "t6": {
        "title": "Fatih Harbiye - Entre Dois Mundos",
        "category": "turca",
        "episodes": 50,
        "description": "Neriman vive entre o mundo tradicional e o moderno.",
        "year": 2013,
    },
    "t7": {
        "title": "Cesur ve Güzel - Brave and Beautiful",
        "category": "turca",
        "episodes": 32,
        "description": "Cesur volta à cidade para vingar a morte de seu pai.",
        "year": 2016,
    },
    "t8": {
        "title": "Não Solte Minha Mão",
        "category": "turca",
        "episodes": 62,
        "description": "Um romance entre um homem rico e uma jovem humilde.",
        "year": 2018,
    },
    "t9": {
        "title": "Aski Memnu - Amor Proibido",
        "category": "turca",
        "episodes": 79,
        "description": "Uma jovem se casa com um homem rico mas se apaixona pelo sobrinho dele.",
        "year": 2008,
    },
    "t10": {
        "title": "Cennet - Paraíso",
        "category": "turca",
        "episodes": 30,
        "description": "Cennet trabalha na empresa do homem que destruiu sua família.",
        "year": 2019,
    },
    # Novelas Mexicanas
    "m1": {
        "title": "Rebelde",
        "category": "mexicana",
        "episodes": 440,
        "description": "Jovens estudantes formam uma banda enquanto enfrentam dramas pessoais.",
        "year": 2004,
    },
    "m2": {
        "title": "Teresa",
        "category": "mexicana",
        "episodes": 152,
        "description": "Uma jovem ambiciosa usa sua beleza para ascender socialmente.",
        "year": 2010,
    },
    "m3": {
        "title": "La Usurpadora",
        "category": "mexicana",
        "episodes": 100,
        "description": "Gêmeas separadas ao nascer trocam de lugar.",
        "year": 1998,
    },
    "m4": {
        "title": "Rubí",
        "category": "mexicana",
        "episodes": 115,
        "description": "Uma mulher bonita e ambiciosa que destrói quem ama por dinheiro.",
        "year": 2004,
    },
    "m5": {
        "title": "María la del Barrio",
        "category": "mexicana",
        "episodes": 90,
        "description": "Uma jovem humilde se casa com um homem rico.",
        "year": 1995,
    },
    "m6": {
        "title": "Pasión de Gavilanes",
        "category": "mexicana",
        "episodes": 188,
        "description": "Três irmãos buscam vingança contra a família Elizondo.",
        "year": 2003,
    },
    "m7": {
        "title": "Avenida Brasil",
        "category": "mexicana",
        "episodes": 179,
        "description": "Nina foi abandonada no lixão pela madrasta e planeja vingança.",
        "year": 2012,
    },
    "m8": {
        "title": "La Rosa de Guadalupe",
        "category": "mexicana",
        "episodes": 200,
        "description": "Histórias de milagres e fé na Virgem de Guadalupe.",
        "year": 2008,
    },
    "m9": {
        "title": "El Señor de los Cielos",
        "category": "mexicana",
        "episodes": 150,
        "description": "A história de Aurelio Casillas, um poderoso traficante.",
        "year": 2013,
    },
    "m10": {
        "title": "Yo Soy Betty, La Fea",
        "category": "mexicana",
        "episodes": 169,
        "description": "Uma mulher brilhante mas considerada feia luta para ser valorizada.",
        "year": 1999,
    },
}

# ─────────────────────────────────────────────
# UTILITÁRIOS JSON
# ─────────────────────────────────────────────
def load_json(filename: Path) -> dict:
    try:
        if filename.exists():
            with filename.open("r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def save_json(filename: Path, data: dict) -> None:
    filename.parent.mkdir(parents=True, exist_ok=True)
    with filename.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# ─────────────────────────────────────────────
# GESTÃO DE USUÁRIOS
# ─────────────────────────────────────────────
def get_user(user_id) -> dict:
    uid = str(user_id)
    users = load_json(USERS_FILE)
    return users.get(uid, {})


def save_user(user_id, data: dict) -> None:
    uid = str(user_id)
    users = load_json(USERS_FILE)
    users[uid] = data
    save_json(USERS_FILE, users)


def ensure_user(user_id, first_name="", username="", referred_by=None) -> dict:
    uid = str(user_id)
    users = load_json(USERS_FILE)

    if uid not in users:
        users[uid] = {
            "joined": datetime.now().isoformat(),
            "first_name": first_name,
            "username": username,
            "is_vip": False,
            "vip_expiry": None,
            "pontos": 0,
            "total_pontos": 0,
            "episodes_watched": 0,
            "watch_streak": 0,
            "last_watch_date": None,
            "last_daily_bonus": None,
            "referred_by": referred_by,
            "referrals": 0,
            "rewards_claimed": [],
        }
        save_json(USERS_FILE, users)
        logger.info(f"Novo usuário registrado: {uid}")

        if referred_by and referred_by != uid and referred_by in users:
            users[referred_by]["referrals"] = users[referred_by].get("referrals", 0) + 1
            users[referred_by]["pontos"] = users[referred_by].get("pontos", 0) + PONTOS_REFERRAL
            users[referred_by]["total_pontos"] = users[referred_by].get("total_pontos", 0) + PONTOS_REFERRAL
            save_json(USERS_FILE, users)
    else:
        user = users[uid]
        if first_name and user.get("first_name") != first_name:
            user["first_name"] = first_name
        if username and user.get("username") != username:
            user["username"] = username
        # Migrate old users
        for key, default in [
            ("pontos", 0), ("total_pontos", 0), ("episodes_watched", 0),
            ("watch_streak", 0), ("last_watch_date", None),
            ("last_daily_bonus", None), ("rewards_claimed", []),
        ]:
            if key not in user:
                user[key] = default
        users[uid] = user
        save_json(USERS_FILE, users)

    return users[uid]


# ─────────────────────────────────────────────
# VIP
# ─────────────────────────────────────────────
def is_vip(user_data: dict) -> bool:
    if not user_data.get("is_vip"):
        return False
    expiry = user_data.get("vip_expiry")
    if expiry is None:
        return True
    return datetime.fromisoformat(expiry) > datetime.now()


def activate_vip(user_id, dias: int) -> None:
    uid = str(user_id)
    users = load_json(USERS_FILE)
    if uid not in users:
        ensure_user(uid)
        users = load_json(USERS_FILE)

    if dias >= 36000:
        users[uid]["vip_expiry"] = None
    else:
        current_expiry = users[uid].get("vip_expiry")
        if current_expiry and datetime.fromisoformat(current_expiry) > datetime.now():
            base = datetime.fromisoformat(current_expiry)
        else:
            base = datetime.now()
        users[uid]["vip_expiry"] = (base + timedelta(days=dias)).isoformat()

    users[uid]["is_vip"] = True
    save_json(USERS_FILE, users)


# ─────────────────────────────────────────────
# SISTEMA DE PONTOS E RECOMPENSAS
# ─────────────────────────────────────────────
def add_points(user_id, pontos: int, reason: str = "") -> int:
    uid = str(user_id)
    users = load_json(USERS_FILE)
    if uid not in users:
        return 0
    users[uid]["pontos"] = users[uid].get("pontos", 0) + pontos
    users[uid]["total_pontos"] = users[uid].get("total_pontos", 0) + pontos
    save_json(USERS_FILE, users)
    logger.info(f"Pontos +{pontos} para {uid} ({reason})")
    return users[uid]["pontos"]


def register_watch(user_id) -> dict:
    uid = str(user_id)
    users = load_json(USERS_FILE)
    if uid not in users:
        return {"pontos_ganhos": 0, "streak": 0}

    user = users[uid]
    today = datetime.now().date().isoformat()
    last_watch = user.get("last_watch_date")

    pontos_ganhos = PONTOS_POR_EPISODIO

    # Streak logic
    if last_watch:
        last_date = datetime.fromisoformat(last_watch).date()
        diff = (datetime.now().date() - last_date).days
        if diff == 1:
            user["watch_streak"] = user.get("watch_streak", 0) + 1
        elif diff > 1:
            user["watch_streak"] = 1
    else:
        user["watch_streak"] = 1

    # Daily bonus
    if user.get("last_daily_bonus") != today:
        pontos_ganhos += PONTOS_BONUS_DIARIO
        user["last_daily_bonus"] = today

    # Streak bonus
    streak = user.get("watch_streak", 0)
    if streak >= 7:
        pontos_ganhos += 15
    elif streak >= 3:
        pontos_ganhos += 5

    user["last_watch_date"] = datetime.now().isoformat()
    user["episodes_watched"] = user.get("episodes_watched", 0) + 1
    user["pontos"] = user.get("pontos", 0) + pontos_ganhos
    user["total_pontos"] = user.get("total_pontos", 0) + pontos_ganhos
    users[uid] = user
    save_json(USERS_FILE, users)

    return {"pontos_ganhos": pontos_ganhos, "streak": streak, "total": user["pontos"]}


def claim_reward(user_id, pontos_necessarios: int) -> bool:
    uid = str(user_id)
    users = load_json(USERS_FILE)
    if uid not in users:
        return False

    user = users[uid]
    if user.get("total_pontos", 0) < pontos_necessarios:
        return False
    if pontos_necessarios in user.get("rewards_claimed", []):
        return False

    user.setdefault("rewards_claimed", []).append(pontos_necessarios)

    # Give VIP days based on reward
    dias_map = {100: 1, 300: 3, 500: 7, 1000: 30, 2500: 36500}
    dias = dias_map.get(pontos_necessarios, 0)
    if dias > 0:
        users[uid] = user
        save_json(USERS_FILE, users)
        activate_vip(user_id, dias)
        return True

    users[uid] = user
    save_json(USERS_FILE, users)
    return True


def should_show_ad(user_data: dict) -> bool:
    if is_vip(user_data):
        return False
    episodes = user_data.get("episodes_watched", 0)
    return episodes > 0 and episodes % AD_INTERVAL_EPISODES == 0


# ─────────────────────────────────────────────
# HISTÓRICO DE VISUALIZAÇÃO
# ─────────────────────────────────────────────
def get_watch_history(user_id) -> list:
    uid = str(user_id)
    history = load_json(WATCH_HISTORY_FILE)
    return history.get(uid, [])


def add_to_history(user_id, novela_id: str, episode: int) -> None:
    uid = str(user_id)
    history = load_json(WATCH_HISTORY_FILE)
    if uid not in history:
        history[uid] = []

    entry = {
        "novela_id": novela_id,
        "episode": episode,
        "watched_at": datetime.now().isoformat(),
    }
    history[uid].append(entry)
    # Keep last 100 entries
    history[uid] = history[uid][-100:]
    save_json(WATCH_HISTORY_FILE, history)


# ─────────────────────────────────────────────
# NOVELAS DATABASE (links de streaming)
# ─────────────────────────────────────────────
def get_novela_links() -> dict:
    return load_json(NOVELAS_FILE)


def set_novela_link(novela_id: str, episode: int, link: str) -> None:
    links = load_json(NOVELAS_FILE)
    key = f"{novela_id}_{episode}"
    links[key] = link
    save_json(NOVELAS_FILE, links)


def get_episode_link(novela_id: str, episode: int) -> str:
    links = load_json(NOVELAS_FILE)
    key = f"{novela_id}_{episode}"
    return links.get(key, "")


# ─────────────────────────────────────────────
# BOT HANDLERS
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        await update.callback_query.answer()

    user = update.effective_user
    referred_by = None

    if context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            referred_by = arg[4:]

    user_data = ensure_user(user.id, user.first_name, user.username or "", referred_by)
    vip = is_vip(user_data)

    vip_badge = "⭐ VIP" if vip else "🆓 Grátis"
    pontos = user_data.get("pontos", 0)

    caption = (
        f"🎬 <b>Novelas Play - Seu Cinema de Novelas!</b>\n\n"
        f"Olá, <b>{user.first_name}</b>! {vip_badge}\n"
        f"💰 Pontos: <b>{pontos}</b>\n\n"
        f"📺 Assista novelas turcas e mexicanas!\n"
        f"💎 Ganhe pontos assistindo e troque por VIP!\n\n"
    )

    if not vip:
        caption += (
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🆓 <b>Plano Grátis:</b> Com anúncios, qualidade SD\n"
            "⭐ <b>Plano VIP:</b> Sem anúncios, Full HD\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
        )

    keyboard = [
        [
            InlineKeyboardButton("🇹🇷 Turcas", callback_data="cat_turca"),
            InlineKeyboardButton("🇲🇽 Mexicanas", callback_data="cat_mexicana"),
        ],
        [InlineKeyboardButton("🔍 Buscar Novela", callback_data="buscar")],
        [
            InlineKeyboardButton("💰 Meus Pontos", callback_data="pontos"),
            InlineKeyboardButton("🎁 Recompensas", callback_data="recompensas"),
        ],
        [
            InlineKeyboardButton("⭐ VIP", callback_data="vip_info"),
            InlineKeyboardButton("👤 Perfil", callback_data="perfil"),
        ],
        [InlineKeyboardButton("🔗 Convidar Amigos", callback_data="referral")],
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        try:
            await update.callback_query.edit_message_caption(
                caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML
            )
            return
        except Exception:
            pass

    try:
        await context.bot.send_photo(
            chat_id=update.effective_chat.id,
            photo=WELCOME_IMAGE_URL,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=caption,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML,
        )


async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    category = query.data.replace("cat_", "")
    cat_name = "🇹🇷 Turcas" if category == "turca" else "🇲🇽 Mexicanas"

    novelas = [
        (nid, info)
        for nid, info in NOVELAS_CATALOG.items()
        if info["category"] == category
    ]

    text = f"<b>{cat_name}</b>\n\nEscolha uma novela:\n"

    keyboard = []
    for nid, info in novelas:
        emoji = "🇹🇷" if category == "turca" else "🇲🇽"
        keyboard.append(
            [InlineKeyboardButton(f"{emoji} {info['title']}", callback_data=f"novela_{nid}")]
        )

    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="voltar_inicio")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_caption(
            caption=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    except Exception:
        await query.edit_message_text(
            text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )


async def novela_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    novela_id = query.data.replace("novela_", "")
    novela = NOVELAS_CATALOG.get(novela_id)

    if not novela:
        await query.edit_message_text("❌ Novela não encontrada.")
        return

    user_data = get_user(query.from_user.id)
    vip = is_vip(user_data)

    quality = "🎬 Full HD" if vip else "📺 SD (Qualidade limitada)"
    ads = "✅ Sem anúncios" if vip else "⚠️ Com anúncios"

    text = (
        f"<b>{novela['title']}</b>\n\n"
        f"📝 {novela['description']}\n\n"
        f"📺 Episódios: <b>{novela['episodes']}</b>\n"
        f"📅 Ano: <b>{novela['year']}</b>\n"
        f"🏷️ Categoria: <b>{novela['category'].capitalize()}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🖥️ Qualidade: {quality}\n"
        f"📢 Anúncios: {ads}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
    )

    # Show episode buttons in pages of 20
    keyboard = []
    total_eps = novela["episodes"]
    page = context.user_data.get(f"page_{novela_id}", 0) if context.user_data else 0
    eps_per_page = 20
    start_ep = page * eps_per_page + 1
    end_ep = min(start_ep + eps_per_page - 1, total_eps)

    text += f"\n📋 Episódios {start_ep}-{end_ep} de {total_eps}:\n"

    row = []
    for ep in range(start_ep, end_ep + 1):
        row.append(
            InlineKeyboardButton(f"{ep}", callback_data=f"watch_{novela_id}_{ep}")
        )
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    # Pagination buttons
    nav_row = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton("⬅️ Anterior", callback_data=f"page_{novela_id}_{page - 1}")
        )
    if end_ep < total_eps:
        nav_row.append(
            InlineKeyboardButton("➡️ Próximo", callback_data=f"page_{novela_id}_{page + 1}")
        )
    if nav_row:
        keyboard.append(nav_row)

    cat = "turca" if novela["category"] == "turca" else "mexicana"
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data=f"cat_{cat}")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_caption(
            caption=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    except Exception:
        await query.edit_message_text(
            text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )


async def page_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    # page_t1_2 -> novela_id=t1, page=2
    novela_id = parts[1]
    page = int(parts[2])

    if context.user_data is None:
        context.user_data = {}
    context.user_data[f"page_{novela_id}"] = page

    # Rebuild the novela detail view
    query.data = f"novela_{novela_id}"
    await novela_detail(update, context)


async def watch_episode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    novela_id = parts[1]
    episode = int(parts[2])

    novela = NOVELAS_CATALOG.get(novela_id)
    if not novela:
        await query.edit_message_text("❌ Novela não encontrada.")
        return

    user_data = ensure_user(query.from_user.id)
    vip = is_vip(user_data)

    # Check if should show ad (free users)
    if should_show_ad(user_data):
        ad_text = (
            "📢 <b>ANÚNCIO</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🌟 Quer assistir SEM anúncios?\n"
            "⭐ Assine o VIP e tenha qualidade FULL HD!\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "⏳ Aguarde 5 segundos...\n\n"
            f"💡 Dica: Ganhe pontos assistindo e troque por VIP grátis!"
        )
        keyboard = [
            [InlineKeyboardButton("⭐ Assinar VIP", callback_data="vip_info")],
            [
                InlineKeyboardButton(
                    "▶️ Continuar Assistindo",
                    callback_data=f"continue_{novela_id}_{episode}",
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await query.edit_message_caption(
                caption=ad_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
            )
        except Exception:
            await query.edit_message_text(
                text=ad_text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
            )
        # Add points for watching ad
        add_points(query.from_user.id, PONTOS_POR_ANUNCIO, "assistiu anúncio")
        return

    await send_episode(update, context, novela_id, episode, novela, vip)


async def continue_watching(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    parts = query.data.split("_")
    novela_id = parts[1]
    episode = int(parts[2])

    novela = NOVELAS_CATALOG.get(novela_id)
    if not novela:
        return

    user_data = get_user(query.from_user.id)
    vip = is_vip(user_data)

    await send_episode(update, context, novela_id, episode, novela, vip)


async def send_episode(update, context, novela_id, episode, novela, vip):
    query = update.callback_query
    user_id = query.from_user.id

    # Get episode link
    link = get_episode_link(novela_id, episode)

    # Register watch and get points
    watch_result = register_watch(user_id)
    add_to_history(user_id, novela_id, episode)

    quality_text = "🎬 Full HD" if vip else "📺 SD"
    pontos_msg = f"+{watch_result['pontos_ganhos']} pontos!"

    if link:
        text = (
            f"▶️ <b>{novela['title']}</b>\n"
            f"📺 Episódio {episode}\n\n"
            f"🖥️ Qualidade: {quality_text}\n"
            f"💰 {pontos_msg}\n"
            f"🔥 Streak: {watch_result['streak']} dias\n\n"
            f"🔗 <a href=\"{link}\">Assistir Agora</a>\n"
        )
    else:
        text = (
            f"▶️ <b>{novela['title']}</b>\n"
            f"📺 Episódio {episode}\n\n"
            f"🖥️ Qualidade: {quality_text}\n"
            f"💰 {pontos_msg}\n"
            f"🔥 Streak: {watch_result['streak']} dias\n\n"
            f"⚠️ Link ainda não disponível.\n"
            f"O admin precisa adicionar o link deste episódio.\n"
            f"Use /solicitar {novela_id} {episode} para pedir ao admin."
        )

    keyboard = []
    if episode < novela["episodes"]:
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"▶️ Próximo Ep. {episode + 1}",
                    callback_data=f"watch_{novela_id}_{episode + 1}",
                )
            ]
        )
    if episode > 1:
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"⏪ Ep. Anterior {episode - 1}",
                    callback_data=f"watch_{novela_id}_{episode - 1}",
                )
            ]
        )

    keyboard.append(
        [InlineKeyboardButton("📋 Lista de Episódios", callback_data=f"novela_{novela_id}")]
    )
    keyboard.append([InlineKeyboardButton("🏠 Menu Principal", callback_data="voltar_inicio")])

    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_caption(
            caption=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    except Exception:
        await query.edit_message_text(
            text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )


# ─────────────────────────────────────────────
# PONTOS E RECOMPENSAS
# ─────────────────────────────────────────────
async def pontos_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_data = ensure_user(query.from_user.id)
    pontos = user_data.get("pontos", 0)
    total = user_data.get("total_pontos", 0)
    streak = user_data.get("watch_streak", 0)
    episodes = user_data.get("episodes_watched", 0)

    # Progress bar
    next_reward = None
    for pts in sorted(RECOMPENSAS.keys()):
        if pts not in user_data.get("rewards_claimed", []):
            next_reward = pts
            break

    progress = ""
    if next_reward:
        pct = min(total / next_reward, 1.0)
        filled = int(pct * 10)
        bar = "🟩" * filled + "⬜" * (10 - filled)
        progress = (
            f"\n🎯 Próxima recompensa: <b>{RECOMPENSAS[next_reward]}</b>\n"
            f"{bar} {total}/{next_reward} pts\n"
        )

    text = (
        f"💰 <b>Seus Pontos</b>\n\n"
        f"💎 Pontos atuais: <b>{pontos}</b>\n"
        f"📊 Total acumulado: <b>{total}</b>\n"
        f"📺 Episódios assistidos: <b>{episodes}</b>\n"
        f"🔥 Streak: <b>{streak} dias</b>\n"
        f"{progress}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Como ganhar pontos:</b>\n"
        f"📺 Assistir episódio: +{PONTOS_POR_EPISODIO} pts\n"
        f"📢 Ver anúncio: +{PONTOS_POR_ANUNCIO} pts\n"
        f"📅 Bônus diário: +{PONTOS_BONUS_DIARIO} pts\n"
        f"🔗 Convidar amigo: +{PONTOS_REFERRAL} pts\n"
        f"🔥 Streak 3+ dias: +5 pts extra\n"
        f"🔥 Streak 7+ dias: +15 pts extra\n"
    )

    keyboard = [
        [InlineKeyboardButton("🎁 Ver Recompensas", callback_data="recompensas")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="voltar_inicio")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_caption(
            caption=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    except Exception:
        await query.edit_message_text(
            text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )


async def recompensas_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_data = ensure_user(query.from_user.id)
    total = user_data.get("total_pontos", 0)
    claimed = user_data.get("rewards_claimed", [])

    text = "🎁 <b>Recompensas</b>\n\nTroque seus pontos por VIP!\n\n"

    keyboard = []
    for pts, reward in sorted(RECOMPENSAS.items()):
        if pts in claimed:
            text += f"✅ <s>{pts} pts — {reward}</s> (Resgatado)\n"
        elif total >= pts:
            text += f"🟢 {pts} pts — {reward} (Disponível!)\n"
            keyboard.append(
                [InlineKeyboardButton(f"🎁 Resgatar: {reward}", callback_data=f"claim_{pts}")]
            )
        else:
            text += f"🔒 {pts} pts — {reward}\n"

    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="voltar_inicio")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_caption(
            caption=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    except Exception:
        await query.edit_message_text(
            text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )


async def claim_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pts = int(query.data.replace("claim_", ""))
    success = claim_reward(query.from_user.id, pts)

    if success:
        reward = RECOMPENSAS.get(pts, "")
        text = (
            f"🎉 <b>Parabéns!</b>\n\n"
            f"Você resgatou: <b>{reward}</b>!\n"
            f"Seu VIP já está ativo! 🌟"
        )
    else:
        text = "❌ Não foi possível resgatar. Verifique se você já não resgatou esta recompensa."

    keyboard = [
        [InlineKeyboardButton("🎁 Recompensas", callback_data="recompensas")],
        [InlineKeyboardButton("🏠 Menu", callback_data="voltar_inicio")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_caption(
            caption=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    except Exception:
        await query.edit_message_text(
            text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )


# ─────────────────────────────────────────────
# VIP INFO
# ─────────────────────────────────────────────
async def vip_info_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_data = ensure_user(query.from_user.id)
    vip = is_vip(user_data)

    if vip:
        expiry = user_data.get("vip_expiry")
        if expiry:
            exp_dt = datetime.fromisoformat(expiry)
            dias_rest = (exp_dt - datetime.now()).days + 1
            status = f"⭐ <b>VIP Ativo</b> — {dias_rest} dia(s) restante(s)"
        else:
            status = "♾️ <b>VIP Vitalício</b>"

        text = (
            f"⭐ <b>Seu Status VIP</b>\n\n"
            f"{status}\n\n"
            f"✅ Sem anúncios\n"
            f"✅ Qualidade Full HD\n"
            f"✅ Acesso a todos os episódios\n"
            f"✅ Downloads disponíveis\n"
        )
    else:
        text = (
            "⭐ <b>Planos VIP</b>\n\n"
            "Assista sem anúncios e em Full HD!\n\n"
            "✅ Sem anúncios no meio da novela\n"
            "✅ Qualidade Full HD\n"
            "✅ Acesso prioritário a novos episódios\n"
            "✅ Downloads para assistir offline\n\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "<b>Planos:</b>\n\n"
        )
        for key, plano in PLANOS_VIP.items():
            text += f"💎 <b>{plano['nome']}</b> — R$ {plano['valor_brl']:.2f} ({plano['dias']} dias)\n"

        text += (
            "\n━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 Ou ganhe VIP grátis acumulando pontos!"
        )

    keyboard = []
    if not vip:
        for key, plano in PLANOS_VIP.items():
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"💳 {plano['nome']} - R${plano['valor_brl']:.2f}",
                        callback_data=f"pagar_{key}",
                    )
                ]
            )

    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="voltar_inicio")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_caption(
            caption=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    except Exception:
        await query.edit_message_text(
            text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )


async def pagar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    plano_key = query.data.replace("pagar_", "")
    plano = PLANOS_VIP.get(plano_key)

    if not plano:
        return

    text = (
        f"💳 <b>Pagamento — {plano['nome']}</b>\n\n"
        f"💰 Valor: <b>R$ {plano['valor_brl']:.2f}</b>\n"
        f"📅 Duração: <b>{plano['dias']} dias</b>\n\n"
        f"Para pagar via PIX:\n"
        f"📱 Entre em contato com o admin para receber a chave PIX.\n\n"
        f"Após o pagamento, envie o comprovante e seu VIP será ativado!"
    )

    keyboard = [
        [InlineKeyboardButton("⭐ Planos", callback_data="vip_info")],
        [InlineKeyboardButton("🏠 Menu", callback_data="voltar_inicio")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_caption(
            caption=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    except Exception:
        await query.edit_message_text(
            text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )


# ─────────────────────────────────────────────
# PERFIL
# ─────────────────────────────────────────────
async def perfil_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    user_data = ensure_user(user.id)
    vip = is_vip(user_data)

    vip_status = "⭐ VIP" if vip else "🆓 Grátis"
    joined = user_data.get("joined", "N/A")
    if joined != "N/A":
        joined = datetime.fromisoformat(joined).strftime("%d/%m/%Y")

    text = (
        f"👤 <b>Seu Perfil</b>\n\n"
        f"📛 Nome: <b>{user.first_name}</b>\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📅 Membro desde: <b>{joined}</b>\n"
        f"💎 Status: <b>{vip_status}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Estatísticas:</b>\n"
        f"📺 Episódios assistidos: <b>{user_data.get('episodes_watched', 0)}</b>\n"
        f"💰 Pontos totais: <b>{user_data.get('total_pontos', 0)}</b>\n"
        f"🔥 Streak atual: <b>{user_data.get('watch_streak', 0)} dias</b>\n"
        f"🔗 Amigos convidados: <b>{user_data.get('referrals', 0)}</b>\n"
    )

    keyboard = [
        [InlineKeyboardButton("📜 Histórico", callback_data="historico")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="voltar_inicio")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_caption(
            caption=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    except Exception:
        await query.edit_message_text(
            text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )


# ─────────────────────────────────────────────
# HISTÓRICO
# ─────────────────────────────────────────────
async def historico_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    history = get_watch_history(query.from_user.id)

    if not history:
        text = "📜 <b>Histórico</b>\n\nVocê ainda não assistiu nenhum episódio."
    else:
        text = "📜 <b>Últimos Assistidos</b>\n\n"
        for entry in reversed(history[-10:]):
            novela = NOVELAS_CATALOG.get(entry["novela_id"], {})
            title = novela.get("title", "Desconhecida")
            ep = entry["episode"]
            date = datetime.fromisoformat(entry["watched_at"]).strftime("%d/%m %H:%M")
            text += f"▶️ {title} — Ep. {ep} ({date})\n"

    keyboard = [
        [InlineKeyboardButton("🔙 Voltar", callback_data="perfil")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_caption(
            caption=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    except Exception:
        await query.edit_message_text(
            text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )


# ─────────────────────────────────────────────
# REFERRAL
# ─────────────────────────────────────────────
async def referral_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    user_data = ensure_user(user_id)
    bot_username = (await context.bot.get_me()).username

    link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    referrals = user_data.get("referrals", 0)

    text = (
        f"🔗 <b>Convide Amigos e Ganhe Pontos!</b>\n\n"
        f"Cada amigo que entrar pelo seu link te dá <b>+{PONTOS_REFERRAL} pontos</b>!\n\n"
        f"👥 Amigos convidados: <b>{referrals}</b>\n"
        f"💰 Pontos ganhos: <b>{referrals * PONTOS_REFERRAL}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📎 Seu link de convite:\n"
        f"<code>{link}</code>\n\n"
        f"Compartilhe com seus amigos! 🚀"
    )

    keyboard = [
        [InlineKeyboardButton("🔙 Voltar", callback_data="voltar_inicio")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_caption(
            caption=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    except Exception:
        await query.edit_message_text(
            text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )


# ─────────────────────────────────────────────
# BUSCAR
# ─────────────────────────────────────────────
async def buscar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    text = (
        "🔍 <b>Buscar Novela</b>\n\n"
        "Digite o nome da novela que deseja buscar.\n\n"
        "Exemplo: <code>Hercai</code> ou <code>Rebelde</code>"
    )

    keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data="voltar_inicio")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await query.edit_message_caption(
            caption=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )
    except Exception:
        await query.edit_message_text(
            text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
        )

    context.user_data["searching"] = True


async def search_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("searching"):
        return

    context.user_data["searching"] = False
    query_text = update.message.text.lower().strip()

    results = []
    for nid, info in NOVELAS_CATALOG.items():
        if query_text in info["title"].lower():
            results.append((nid, info))

    if not results:
        text = f"🔍 Nenhuma novela encontrada para: <b>{query_text}</b>"
        keyboard = [[InlineKeyboardButton("🔍 Buscar Novamente", callback_data="buscar")]]
    else:
        text = f"🔍 Resultados para: <b>{query_text}</b>\n\n"
        keyboard = []
        for nid, info in results:
            emoji = "🇹🇷" if info["category"] == "turca" else "🇲🇽"
            keyboard.append(
                [InlineKeyboardButton(f"{emoji} {info['title']}", callback_data=f"novela_{nid}")]
            )

    keyboard.append([InlineKeyboardButton("🏠 Menu", callback_data="voltar_inicio")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        text=text, reply_markup=reply_markup, parse_mode=ParseMode.HTML
    )


# ─────────────────────────────────────────────
# ADMIN COMMANDS
# ─────────────────────────────────────────────
async def admin_add_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("❌ Apenas o admin pode usar este comando.")
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "Uso: /addlink <novela_id> <episodio> <link>\n"
            "Exemplo: /addlink t1 5 https://streamlink.com/ep5"
        )
        return

    novela_id = context.args[0]
    episode = int(context.args[1])
    link = context.args[2]

    if novela_id not in NOVELAS_CATALOG:
        await update.message.reply_text(f"❌ Novela '{novela_id}' não encontrada.")
        return

    set_novela_link(novela_id, episode, link)
    novela = NOVELAS_CATALOG[novela_id]
    await update.message.reply_text(
        f"✅ Link adicionado!\n"
        f"📺 {novela['title']} — Ep. {episode}\n"
        f"🔗 {link}"
    )


async def admin_add_links_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("❌ Apenas o admin pode usar este comando.")
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "Uso: /addlinks <novela_id> <ep_inicio> <link1> <link2> ...\n"
            "Exemplo: /addlinks t1 1 link1 link2 link3"
        )
        return

    novela_id = context.args[0]
    ep_inicio = int(context.args[1])
    links = context.args[2:]

    if novela_id not in NOVELAS_CATALOG:
        await update.message.reply_text(f"❌ Novela '{novela_id}' não encontrada.")
        return

    for i, link in enumerate(links):
        set_novela_link(novela_id, ep_inicio + i, link)

    novela = NOVELAS_CATALOG[novela_id]
    await update.message.reply_text(
        f"✅ {len(links)} links adicionados!\n"
        f"📺 {novela['title']} — Eps. {ep_inicio} a {ep_inicio + len(links) - 1}"
    )


async def admin_vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("❌ Apenas o admin pode usar este comando.")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Uso: /darvip <user_id> <dias>\n"
            "Exemplo: /darvip 123456789 30"
        )
        return

    target_id = context.args[0]
    dias = int(context.args[1])
    activate_vip(target_id, dias)

    await update.message.reply_text(
        f"✅ VIP ativado para {target_id} por {dias} dias!"
    )


async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("❌ Apenas o admin pode usar este comando.")
        return

    users = load_json(USERS_FILE)
    total_users = len(users)
    vip_users = sum(1 for u in users.values() if is_vip(u))
    total_watches = sum(u.get("episodes_watched", 0) for u in users.values())

    text = (
        f"📊 <b>Estatísticas do Bot</b>\n\n"
        f"👥 Total de usuários: <b>{total_users}</b>\n"
        f"⭐ Usuários VIP: <b>{vip_users}</b>\n"
        f"📺 Total de episódios assistidos: <b>{total_watches}</b>\n"
        f"🆓 Usuários grátis: <b>{total_users - vip_users}</b>\n"
    )

    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def admin_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != ADMIN_ID:
        await update.message.reply_text("❌ Apenas o admin pode usar este comando.")
        return

    if not context.args:
        await update.message.reply_text("Uso: /broadcast <mensagem>")
        return

    msg = " ".join(context.args)
    users = load_json(USERS_FILE)
    sent = 0
    failed = 0

    for uid in users:
        try:
            await context.bot.send_message(
                chat_id=int(uid), text=msg, parse_mode=ParseMode.HTML
            )
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"📢 Broadcast enviado!\n✅ Enviados: {sent}\n❌ Falhas: {failed}"
    )


async def solicitar_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text(
            "Uso: /solicitar <novela_id> <episodio>\n"
            "Exemplo: /solicitar t1 5"
        )
        return

    novela_id = context.args[0]
    episode = context.args[1]
    novela = NOVELAS_CATALOG.get(novela_id)

    if not novela:
        await update.message.reply_text("❌ Novela não encontrada.")
        return

    user = update.effective_user
    if ADMIN_ID:
        try:
            await context.bot.send_message(
                chat_id=int(ADMIN_ID),
                text=(
                    f"📥 <b>Solicitação de Episódio</b>\n\n"
                    f"👤 De: {user.first_name} (<code>{user.id}</code>)\n"
                    f"📺 Novela: {novela['title']}\n"
                    f"🎬 Episódio: {episode}"
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

    await update.message.reply_text(
        f"✅ Solicitação enviada!\n"
        f"O admin será notificado para adicionar o episódio {episode} de {novela['title']}."
    )


# ─────────────────────────────────────────────
# VOLTAR AO INÍCIO
# ─────────────────────────────────────────────
async def voltar_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


# ─────────────────────────────────────────────
# CALLBACK ROUTER
# ─────────────────────────────────────────────
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("cat_"):
        await category_handler(update, context)
    elif data.startswith("novela_"):
        await novela_detail(update, context)
    elif data.startswith("watch_"):
        await watch_episode(update, context)
    elif data.startswith("continue_"):
        await continue_watching(update, context)
    elif data.startswith("page_"):
        await page_handler(update, context)
    elif data == "pontos":
        await pontos_handler(update, context)
    elif data == "recompensas":
        await recompensas_handler(update, context)
    elif data.startswith("claim_"):
        await claim_handler(update, context)
    elif data == "vip_info":
        await vip_info_handler(update, context)
    elif data.startswith("pagar_"):
        await pagar_handler(update, context)
    elif data == "perfil":
        await perfil_handler(update, context)
    elif data == "historico":
        await historico_handler(update, context)
    elif data == "referral":
        await referral_handler(update, context)
    elif data == "buscar":
        await buscar_handler(update, context)
    elif data == "voltar_inicio":
        await voltar_inicio(update, context)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def main():
    if not TOKEN:
        logger.error("BOT_TOKEN não configurado!")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addlink", admin_add_link))
    app.add_handler(CommandHandler("addlinks", admin_add_links_bulk))
    app.add_handler(CommandHandler("darvip", admin_vip))
    app.add_handler(CommandHandler("stats", admin_stats))
    app.add_handler(CommandHandler("broadcast", admin_broadcast))
    app.add_handler(CommandHandler("solicitar", solicitar_handler))

    # Callbacks
    app.add_handler(CallbackQueryHandler(callback_router))

    # Text messages (search)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_message))

    logger.info("🎬 Novelas Play Bot iniciado!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
