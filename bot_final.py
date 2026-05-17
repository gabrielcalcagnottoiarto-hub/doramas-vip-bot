import os
import json
import logging
import asyncio
import random
import time
import urllib.parse
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from telegram.constants import ParseMode

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIGURAÇÕES
# ─────────────────────────────────────────────
TOKEN           = os.environ.get("BOT_TOKEN",       "SEU_TOKEN_AQUI")
ADMIN_ID        = os.environ.get("ADMIN_ID",        "SEU_ADMIN_ID_AQUI")
MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN", "")   # Mercado Pago
TONCENTER_KEY   = os.environ.get("TONCENTER_KEY",   "")   # TON Center API Key (opcional)

TON_ADDRESS = "UQDn8qu6wduopti68NN9aFjJ0ORN8diPtuUMuR8_7tQG7lai"

PLANOS = {
    "mensal":     {"nome": "Mensal",     "valor_brl": 15.00,  "valor_ton": 3.0,  "dias": 30},
    "trimestral": {"nome": "Trimestral", "valor_brl": 35.00,  "valor_ton": 7.0,  "dias": 90},
    "anual":      {"nome": "Anual",      "valor_brl": 100.00, "valor_ton": 20.0, "dias": 365},
}

TRIAL_DAYS    = 3
MIN_REFERRALS = 5
REFERRAL_DAYS = 30

PIX_EXPIRY_MINUTES = 30
PIX_CHECK_INTERVAL = 20   # seg

TON_EXPIRY_MINUTES = 30
TON_CHECK_INTERVAL = 30   # seg
TON_TOLERANCE      = 0.01 # tolerância de ±0.01 TON

# ─────────────────────────────────────────────
# CAMINHOS
# ─────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
DATA_FILE     = BASE_DIR / "users.json"
VIDEO_DB      = BASE_DIR / "video_links.json"
CONFIG_FILE   = BASE_DIR / "config.json"
PAYMENTS_FILE = BASE_DIR / "payments.json"   # PIX + TON pendentes

WELCOME_IMAGE_URL = (
    "https://img.freepik.com/vetores-premium/"
    "ilustracao-de-estilo-anime-de-um-casal-em-um-encontro-romantico_23-2148817840.jpg"
)
WELCOME_VIDEO  = BASE_DIR / "welcome_video.mp4"

# ─────────────────────────────────────────────
# CATÁLOGO
# ─────────────────────────────────────────────
titles = [
    "Pousando no Amor", "Beleza Verdadeira", "A Lenda do Mar Azul", "Sorriso Real",
    "Meu Demônio Favorito", "Rainha das Lágrimas", "Tudo Bem Não Ser Normal",
    "Amor Rural", "Romance is a Bonus Book", "A Lição", "Vincenzo",
    "All of Us Are Dead", "A Criatura de Gyeongseong", "Classe dos Heróis Fracos",
    "Extracurricular", "Flor do Mal", "Alquimia das Almas", "Goblin",
    "Mr. Sunshine", "O Palhaço Coroado", "Meow, The Secret Boy"
]
DORAMAS_CATALOG = {
    f"d{i+1}": {"title": t, "episodes": 21 if t == "A Lenda do Mar Azul" else 16}
    for i, t in enumerate(titles)
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
# CONFIG
# ─────────────────────────────────────────────
def get_min_referrals() -> int:
    return int(load_json(CONFIG_FILE).get("min_referrals", MIN_REFERRALS))

def set_min_referrals(value: int) -> None:
    cfg = load_json(CONFIG_FILE)
    cfg["min_referrals"] = value
    save_json(CONFIG_FILE, cfg)

# ─────────────────────────────────────────────
# MIGRAÇÃO DE USUÁRIO
# ─────────────────────────────────────────────
def migrate_user(user: dict) -> dict:
    defaults = {
        "is_vip": False, "vip_expiry": None, "trial_expiry": None,
        "referred_by": None, "referrals": 0, "referral_unlocked": False,
        "referral_unlock_expiry": None, "username": "", "first_name": "",
    }
    for k, v in defaults.items():
        if k not in user:
            user[k] = v
    return user

# ─────────────────────────────────────────────
# USUÁRIOS / VIP
# ─────────────────────────────────────────────
def ensure_user(user_id, referred_by=None, first_name="", username="") -> tuple:
    uid   = str(user_id)
    users = load_json(DATA_FILE)
    is_new = uid not in users
    notif_ref_id, notif_ref_data = None, None

    if is_new:
        trial_expiry = (datetime.now() + timedelta(days=TRIAL_DAYS)).isoformat()
        users[uid] = {
            "joined": datetime.now().isoformat(),
            "is_vip": False, "vip_expiry": None,
            "trial_expiry": trial_expiry,
            "referred_by": referred_by, "referrals": 0,
            "referral_unlocked": False, "referral_unlock_expiry": None,
            "first_name": first_name, "username": username,
        }
        save_json(DATA_FILE, users)
        logger.info(f"Novo usuário {uid} — trial até {trial_expiry}")

        if referred_by and referred_by != uid:
            users = load_json(DATA_FILE)
            if referred_by in users:
                users[referred_by]["referrals"] = users[referred_by].get("referrals", 0) + 1
                min_ref = get_min_referrals()
                if (users[referred_by]["referrals"] >= min_ref
                        and not users[referred_by].get("referral_unlocked")):
                    unlock_expiry = (datetime.now() + timedelta(days=REFERRAL_DAYS)).isoformat()
                    users[referred_by]["referral_unlocked"] = True
                    users[referred_by]["referral_unlock_expiry"] = unlock_expiry
                save_json(DATA_FILE, users)
                notif_ref_id   = referred_by
                notif_ref_data = users[referred_by]
    else:
        user = migrate_user(users[uid])
        changed = False
        if first_name and user.get("first_name") != first_name:
            user["first_name"] = first_name; changed = True
        if username and user.get("username") != username:
            user["username"] = username; changed = True
        users[uid] = user
        if changed:
            save_json(DATA_FILE, users)

    return load_json(DATA_FILE).get(uid, {}), notif_ref_id, notif_ref_data

def is_vip_active(user_data: dict) -> bool:
    if user_data.get("is_vip"):
        expiry = user_data.get("vip_expiry")
        if expiry is None or datetime.fromisoformat(expiry) > datetime.now():
            return True
    trial = user_data.get("trial_expiry")
    if trial and datetime.fromisoformat(trial) > datetime.now():
        return True
    if user_data.get("referral_unlocked"):
        ref_expiry = user_data.get("referral_unlock_expiry")
        if ref_expiry is None or datetime.fromisoformat(ref_expiry) > datetime.now():
            return True
    return False

def vip_status_text(user_data: dict) -> str:
    trial = user_data.get("trial_expiry")
    if trial:
        t_dt = datetime.fromisoformat(trial)
        if t_dt > datetime.now():
            return f"🎁 <b>Trial grátis</b> — {(t_dt - datetime.now()).days + 1} dia(s) restante(s)"
    if user_data.get("is_vip"):
        expiry = user_data.get("vip_expiry")
        if expiry is None:
            return "♾️ <b>VIP Vitalício</b>"
        exp_dt = datetime.fromisoformat(expiry)
        if exp_dt > datetime.now():
            return f"💎 <b>VIP ativo</b> — expira em {(exp_dt - datetime.now()).days + 1} dia(s)"
    if user_data.get("referral_unlocked"):
        ref_expiry = user_data.get("referral_unlock_expiry")
        if ref_expiry:
            ref_dt = datetime.fromisoformat(ref_expiry)
            if ref_dt > datetime.now():
                return f"🔗 <b>Acesso por convites</b> — {(ref_dt - datetime.now()).days + 1} dia(s)"
        else:
            return "🔗 <b>Acesso desbloqueado por referências!</b>"
    return "🔒 <b>Sem acesso ativo</b> — assine o VIP ou convide amigos!"

def activate_vip(user_id, dias: int) -> None:
    uid   = str(user_id)
    users = load_json(DATA_FILE)
    if uid not in users:
        ensure_user(uid); users = load_json(DATA_FILE)
    expiry = None if dias >= 36000 else (datetime.now() + timedelta(days=dias)).isoformat()
    users[uid]["is_vip"]     = True
    users[uid]["vip_expiry"] = expiry
    save_json(DATA_FILE, users)

# ─────────────────────────────────────────────
# REFERÊNCIAS
# ─────────────────────────────────────────────
def get_referral_link(bot_username: str, user_id) -> str:
    return f"https://t.me/{bot_username}?start=ref_{user_id}"

def referral_progress_text(user_data: dict) -> str:
    referrals = user_data.get("referrals", 0)
    min_ref   = get_min_referrals()
    if user_data.get("referral_unlocked"):
        ref_expiry = user_data.get("referral_unlock_expiry")
        if ref_expiry:
            ref_dt    = datetime.fromisoformat(ref_expiry)
            remaining = max((ref_dt - datetime.now()).days + 1, 0)
            if ref_dt <= datetime.now():
                return f"⏰ <b>Acesso por convites expirado.</b>\nConvide mais {min_ref} pessoas ou assine o VIP!"
            return (f"✅ <b>Acesso liberado por convites!</b>\n"
                    f"Você convidou <b>{referrals}</b> pessoa(s) 🎉\n"
                    f"⏳ Expira em <b>{remaining} dia(s)</b>")
        return f"✅ <b>Acesso liberado por convites!</b>\nVocê convidou <b>{referrals}</b> pessoa(s) 🎉"
    remaining  = min_ref - referrals
    bar_filled = int((referrals / min_ref) * 10) if min_ref > 0 else 0
    bar        = "🟩" * bar_filled + "⬜" * (10 - bar_filled)
    return (f"🔗 <b>Seu Progresso de Convites</b>\n\n{bar}\n"
            f"<b>{referrals} / {min_ref}</b> pessoas convidadas\n\n"
            f"Faltam <b>{remaining}</b> convite(s) para desbloquear o acesso gratuito! 🚀")

# ─────────────────────────────────────────────
# MERCADO PAGO — PIX AUTOMÁTICO
# ─────────────────────────────────────────────
async def criar_pix_mp(plano_key: str, user_id: str) -> dict | None:
    if not MP_ACCESS_TOKEN:
        return None
    plano = PLANOS[plano_key]
    payload = {
        "transaction_amount": plano["valor_brl"],
        "description":        f"DORAMAS VIP — Plano {plano['nome']}",
        "payment_method_id":  "pix",
        "payer":              {"email": f"user{user_id}@doramasvip.com"},
        "metadata":           {"user_id": user_id, "plano": plano_key},
        "date_of_expiration": (datetime.now() + timedelta(minutes=PIX_EXPIRY_MINUTES)
                               ).strftime("%Y-%m-%dT%H:%M:%S.000-03:00"),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.mercadopago.com/v1/payments",
                json=payload,
                headers={
                    "Authorization":    f"Bearer {MP_ACCESS_TOKEN}",
                    "Content-Type":     "application/json",
                    "X-Idempotency-Key": f"dvip-{user_id}-{plano_key}-{int(time.time())}",
                },
            )
        data = resp.json()
        if resp.status_code in (200, 201):
            tid = data["point_of_interaction"]["transaction_data"]
            return {
                "type":       "pix",
                "payment_id": str(data["id"]),
                "qr_code":    tid.get("qr_code", ""),
                "qr_base64":  tid.get("qr_code_base64", ""),
                "plano":      plano_key,
                "user_id":    user_id,
                "created_at": datetime.now().isoformat(),
            }
        logger.error(f"MP erro {resp.status_code}: {data}")
    except Exception as e:
        logger.error(f"Erro ao criar PIX MP: {e}")
    return None

async def verificar_pagamento_mp(payment_id: str) -> str:
    if not MP_ACCESS_TOKEN:
        return "unknown"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.mercadopago.com/v1/payments/{payment_id}",
                headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}"},
            )
        return resp.json().get("status", "unknown")
    except Exception as e:
        logger.warning(f"Erro ao verificar PIX {payment_id}: {e}")
        return "unknown"

# ─────────────────────────────────────────────
# TON — PAGAMENTO AUTOMÁTICO
# ─────────────────────────────────────────────
def gerar_referencia_ton(user_id: str, plano_key: str) -> str:
    """Gera código único de referência para identificar o pagamento TON."""
    ts = int(time.time()) % 100000
    return f"DVIP-{user_id[-4:]}-{plano_key[:3].upper()}-{ts}"

def tonkeeper_url(address: str, nanotons: int, memo: str) -> str:
    """Gera URL do Tonkeeper com memo para rastreamento."""
    memo_enc = urllib.parse.quote(memo)
    return f"https://app.tonkeeper.com/transfer/{address}?amount={nanotons}&text={memo_enc}"

async def verificar_pagamento_ton(referencia: str, valor_ton: float) -> bool:
    """
    Verifica na blockchain TON se chegou uma transação com o memo correto
    e valor aproximado ao esperado.
    Usa TON Center API v2.
    """
    url = "https://toncenter.com/api/v2/getTransactions"
    params = {
        "address": TON_ADDRESS,
        "limit":   30,
        "to_lt":   0,
    }
    if TONCENTER_KEY:
        params["api_key"] = TONCENTER_KEY

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, params=params)
        data = resp.json()
        if not data.get("ok"):
            return False

        valor_nanotons = int(valor_ton * 1e9)
        tolerancia_nano = int(TON_TOLERANCE * 1e9)

        for tx in data.get("result", []):
            in_msg = tx.get("in_msg", {})
            msg_text = in_msg.get("message", "")
            value    = int(in_msg.get("value", 0))

            # Verifica se o memo bate e o valor está dentro da tolerância
            if referencia in msg_text and abs(value - valor_nanotons) <= tolerancia_nano:
                logger.info(f"✅ TON pago! ref={referencia} valor={value/1e9:.4f} TON")
                return True
    except Exception as e:
        logger.warning(f"Erro ao verificar TON: {e}")
    return False

# ─────────────────────────────────────────────
# PAGAMENTOS PENDENTES
# ─────────────────────────────────────────────
def salvar_pagamento(payment_data: dict) -> None:
    payments = load_json(PAYMENTS_FILE)
    key = payment_data.get("payment_id") or payment_data.get("referencia")
    payments[key] = payment_data
    save_json(PAYMENTS_FILE, payments)

def remover_pagamento(key: str) -> None:
    payments = load_json(PAYMENTS_FILE)
    payments.pop(key, None)
    save_json(PAYMENTS_FILE, payments)

# ─────────────────────────────────────────────
# MONITOR PIX
# ─────────────────────────────────────────────
async def monitorar_pix(payment_id: str, user_id: str, plano_key: str,
                         context: ContextTypes.DEFAULT_TYPE) -> None:
    plano    = PLANOS[plano_key]
    deadline = datetime.now() + timedelta(minutes=PIX_EXPIRY_MINUTES)

    while datetime.now() < deadline:
        await asyncio.sleep(PIX_CHECK_INTERVAL)
        status = await verificar_pagamento_mp(payment_id)
        logger.info(f"PIX {payment_id} — {status}")

        if status == "approved":
            activate_vip(user_id, plano["dias"])
            remover_pagamento(payment_id)
            await _notificar_pagamento_aprovado(context, user_id, plano, "PIX", payment_id)
            return

        if status in ("rejected", "cancelled"):
            remover_pagamento(payment_id)
            await _notificar_pagamento_recusado(context, user_id)
            return

    remover_pagamento(payment_id)
    await _notificar_pagamento_expirado(context, user_id)

# ─────────────────────────────────────────────
# MONITOR TON
# ─────────────────────────────────────────────
async def monitorar_ton(referencia: str, user_id: str, plano_key: str,
                         context: ContextTypes.DEFAULT_TYPE) -> None:
    plano    = PLANOS[plano_key]
    deadline = datetime.now() + timedelta(minutes=TON_EXPIRY_MINUTES)

    while datetime.now() < deadline:
        await asyncio.sleep(TON_CHECK_INTERVAL)
        pago = await verificar_pagamento_ton(referencia, plano["valor_ton"])

        if pago:
            activate_vip(user_id, plano["dias"])
            remover_pagamento(referencia)
            await _notificar_pagamento_aprovado(context, user_id, plano, "TON", referencia)
            return

    remover_pagamento(referencia)
    await _notificar_pagamento_expirado(context, user_id)

# ─────────────────────────────────────────────
# NOTIFICAÇÕES DE PAGAMENTO
# ─────────────────────────────────────────────
async def _notificar_pagamento_aprovado(context, user_id: str, plano: dict,
                                         metodo: str, ref: str) -> None:
    emoji = "💳" if metodo == "PIX" else "💎"
    try:
        await context.bot.send_message(
            chat_id=int(user_id),
            text=(
                f"✅ <b>Pagamento confirmado!</b>\n\n"
                f"{emoji} Método: <b>{metodo}</b>\n"
                f"📅 Plano: <b>{plano['nome']}</b>\n"
                f"🎉 Aproveite <b>{plano['dias']} dias</b> de acesso ilimitado! 🍿\n\n"
                "Use /start para acessar o catálogo."
            ),
            parse_mode=ParseMode.HTML,
        )
        await context.bot.send_message(
            chat_id=int(ADMIN_ID),
            text=(
                f"💰 <b>Pagamento aprovado!</b>\n\n"
                f"👤 User: <code>{user_id}</code>\n"
                f"📅 Plano: <b>{plano['nome']}</b>\n"
                f"{emoji} Método: <b>{metodo}</b>\n"
                f"🔑 Ref: <code>{ref}</code>"
            ),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.warning(f"Erro ao notificar aprovação: {e}")

async def _notificar_pagamento_recusado(context, user_id: str) -> None:
    try:
        await context.bot.send_message(
            chat_id=int(user_id),
            text="❌ <b>Pagamento não aprovado.</b>\n\nTente novamente em /start → Planos VIP.",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass

async def _notificar_pagamento_expirado(context, user_id: str) -> None:
    try:
        await context.bot.send_message(
            chat_id=int(user_id),
            text="⏰ <b>Pagamento expirado.</b>\n\nGere um novo em /start → Planos VIP.",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass

# ─────────────────────────────────────────────
# HELPERS DE ENVIO
# ─────────────────────────────────────────────
async def send_or_edit_photo(update, context, caption: str, keyboard: list) -> None:
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.callback_query:
        try:
            await update.callback_query.edit_message_caption(
                caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML,
            )
            return
        except Exception:
            pass

    chat_id = update.effective_chat.id

    # Try cached welcome video first
    cached_vid = load_json(CONFIG_FILE).get("welcome_video_id")
    if cached_vid:
        try:
            await context.bot.send_video(
                chat_id=chat_id, video=cached_vid,
                caption=caption, reply_markup=reply_markup,
                parse_mode=ParseMode.HTML, read_timeout=60, write_timeout=60,
            )
            return
        except Exception:
            pass

    # Try sending local welcome video file
    if WELCOME_VIDEO.exists():
        try:
            with WELCOME_VIDEO.open("rb") as v:
                sent = await context.bot.send_video(
                    chat_id=chat_id, video=v,
                    caption=caption, reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML, read_timeout=120, write_timeout=120,
                )
                cfg = load_json(CONFIG_FILE)
                cfg["welcome_video_id"] = sent.video.file_id
                save_json(CONFIG_FILE, cfg)
            return
        except Exception:
            pass

    # Fallback to welcome image
    try:
        await context.bot.send_photo(
            chat_id=chat_id, photo=WELCOME_IMAGE_URL,
            caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML,
        )
    except Exception:
        await context.bot.send_message(
            chat_id=chat_id, text=caption,
            reply_markup=reply_markup, parse_mode=ParseMode.HTML,
        )

# ─────────────────────────────────────────────
# START
# ─────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.callback_query:
            await update.callback_query.answer()

        referred_by = None
        if context.args:
            arg = context.args[0]
            if arg.startswith("ref_"):
                referred_by = arg[4:]

        user = update.effective_user
        user_data, notif_ref_id, notif_ref_data = ensure_user(
            user.id, referred_by=referred_by,
            first_name=user.first_name or "", username=user.username or "",
        )
        status = vip_status_text(user_data)

        if notif_ref_id and notif_ref_data:
            min_ref   = get_min_referrals()
            ref_count = notif_ref_data.get("referrals", 0)
            new_name  = user.first_name or "Alguém"
            if notif_ref_data.get("referral_unlocked"):
                ref_exp   = notif_ref_data.get("referral_unlock_expiry", "")
                exp_label = ""
                if ref_exp:
                    exp_dt    = datetime.fromisoformat(ref_exp)
                    exp_label = f"\n📅 Válido até {exp_dt.strftime('%d/%m/%Y')}"
                notif_text = (
                    f"🎉 <b>Acesso desbloqueado!</b>\n\n"
                    f"👤 <b>{new_name}</b> entrou pelo seu link.\n"
                    f"✅ {ref_count}/{min_ref} convites — acesso liberado! 🔓{exp_label}"
                )
            else:
                notif_text = (
                    f"🔔 <b>Novo convite!</b>\n\n"
                    f"👤 <b>{new_name}</b> entrou pelo seu link.\n"
                    f"📊 {ref_count}/{min_ref} — faltam {min_ref - ref_count} convite(s)!"
                )
            try:
                await context.bot.send_message(
                    chat_id=notif_ref_id, text=notif_text, parse_mode=ParseMode.HTML)
            except Exception as e:
                logger.warning(f"Não foi possível notificar {notif_ref_id}: {e}")

        caption = (
            "✨ <b>DORAMAS VIP</b> 🍿\n\n"
            f"{status}\n\n"
            "🎁 Novos usuários ganham <b>3 dias grátis</b> automaticamente!\n"
            "🔗 Convide amigos e ganhe acesso gratuito!\n"
            "💎 Assine o VIP para acesso ilimitado\n\n"
            "Escolha uma opção:"
        )
        keyboard = [
            [InlineKeyboardButton("📂 Catálogo",            callback_data="cat_0")],
            [InlineKeyboardButton("💎 Planos VIP",          callback_data="vip")],
            [InlineKeyboardButton("🔗 Meu Link de Convite", callback_data="referral")],
            [InlineKeyboardButton("ℹ️ Meu Status",          callback_data="status")],
        ]
        await send_or_edit_photo(update, context, caption, keyboard)
    except Exception as e:
        logger.error(f"Erro no start: {e}")

# ─────────────────────────────────────────────
# REFERRAL
# ─────────────────────────────────────────────
async def referral_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_data, _, _ = ensure_user(query.from_user.id)
    bot_username     = (await context.bot.get_me()).username
    link             = get_referral_link(bot_username, query.from_user.id)
    progress         = referral_progress_text(user_data)
    min_ref          = get_min_referrals()
    text = (
        f"🔗 <b>SEU LINK DE CONVITE</b>\n\n{progress}\n\n"
        f"📲 <b>Compartilhe:</b>\n<code>{link}</code>\n\n"
        f"👥 Ao atingir <b>{min_ref} convite(s)</b> você desbloqueia acesso gratuito!"
    )
    keyboard = [
        [InlineKeyboardButton("📋 Copiar Link", switch_inline_query=link)],
        [InlineKeyboardButton("🏠 Início",      callback_data="home")],
    ]
    await query.edit_message_caption(
        caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML)

# ─────────────────────────────────────────────
# STATUS
# ─────────────────────────────────────────────
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_data, _, _ = ensure_user(query.from_user.id)
    keyboard = [
        [InlineKeyboardButton("📂 Catálogo",            callback_data="cat_0")],
        [InlineKeyboardButton("🔗 Meu Link de Convite", callback_data="referral")],
        [InlineKeyboardButton("💎 Assinar VIP",         callback_data="vip")],
        [InlineKeyboardButton("🏠 Início",              callback_data="home")],
    ]
    await query.edit_message_caption(
        caption=(f"👤 <b>Seu Acesso</b>\n\n"
                 f"{vip_status_text(user_data)}\n\n"
                 f"{referral_progress_text(user_data)}"),
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML,
    )

# ─────────────────────────────────────────────
# CATÁLOGO
# ─────────────────────────────────────────────
async def catalog_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page  = int(query.data.split("_")[1])
    d_ids = list(DORAMAS_CATALOG.keys())
    keyboard = [
        [InlineKeyboardButton(DORAMAS_CATALOG[d]["title"], callback_data=f"view_{d}_0")]
        for d in d_ids[page * 8:(page + 1) * 8]
    ]
    nav = []
    if page > 0:                 nav.append(InlineKeyboardButton("⬅️", callback_data=f"cat_{page-1}"))
    if (page+1)*8 < len(d_ids):  nav.append(InlineKeyboardButton("➡️", callback_data=f"cat_{page+1}"))
    if nav: keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("🏠 Início", callback_data="home")])
    await query.edit_message_caption(
        caption="📂 <b>CATÁLOGO DE DORAMAS</b>",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML,
    )

# ─────────────────────────────────────────────
# EPISÓDIOS
# ─────────────────────────────────────────────
async def view_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, d_id, _ = query.data.split("_")
    dorama = DORAMAS_CATALOG[d_id]
    keyboard, row = [], []
    for ep in range(1, dorama["episodes"] + 1):
        row.append(InlineKeyboardButton(str(ep), callback_data=f"play_{d_id}_{ep}"))
        if len(row) == 5: keyboard.append(row); row = []
    if row: keyboard.append(row)
    keyboard.append([InlineKeyboardButton("⬅️ Catálogo", callback_data="cat_0")])
    keyboard.append([InlineKeyboardButton("🏠 Início",    callback_data="home")])
    await query.edit_message_caption(
        caption=f"🎬 <b>{dorama['title']}</b>\nEscolha o episódio:",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML,
    )

# ─────────────────────────────────────────────
# REPRODUZIR
# ─────────────────────────────────────────────
async def play_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    try:
        _, d_id, ep = query.data.split("_")
        user_data, _, _ = ensure_user(query.from_user.id)

        if not is_vip_active(user_data):
            bot_username = (await context.bot.get_me()).username
            link         = get_referral_link(bot_username, query.from_user.id)
            min_ref      = get_min_referrals()
            referrals    = user_data.get("referrals", 0)
            keyboard = [
                [InlineKeyboardButton("💎 Ver Planos VIP",      callback_data="vip")],
                [InlineKeyboardButton("🔗 Meu Link de Convite", callback_data="referral")],
                [InlineKeyboardButton("🏠 Início",              callback_data="home")],
            ]
            await query.edit_message_caption(
                caption=(
                    "🔒 <b>Conteúdo Exclusivo VIP</b>\n\nSeu período de teste expirou.\n\n"
                    f"💡 <b>Grátis:</b> convide <b>{min_ref - referrals}</b> pessoa(s):\n"
                    f"<code>{link}</code>\n\nOu assine um plano VIP! 💎"
                ),
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML,
            )
            return

        db        = load_json(VIDEO_DB)
        video_url = db.get(f"{d_id}_{ep}", "")
        title     = DORAMAS_CATALOG[d_id]["title"]

        if not video_url or video_url.strip() in ("", "COLOQUE_O_FILE_ID_AQUI"):
            await query.edit_message_caption(
                caption=f"⏳ <b>{title}</b> — Ep {ep}\n\nAinda não disponível. Em breve! 🙏",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("⬅️ Voltar", callback_data=f"view_{d_id}_0")]]),
                parse_mode=ParseMode.HTML,
            )
            return

        await query.edit_message_caption(
            caption=f"🎬 <b>{title}</b> — Episódio {ep}\n\nClique para assistir:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"▶️ Assistir Ep {ep}", url=video_url)],
                [InlineKeyboardButton("⬅️ Voltar", callback_data=f"view_{d_id}_0")],
            ]),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.error(f"Erro no play: {e}")

# ─────────────────────────────────────────────
# VIP — LISTA DE PLANOS
# ─────────────────────────────────────────────
async def vip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("📅 Mensal — R$ 15,00 | 3 TON",      callback_data="plan_mensal")],
        [InlineKeyboardButton("🗓️ Trimestral — R$ 35,00 | 7 TON",  callback_data="plan_trimestral")],
        [InlineKeyboardButton("📆 Anual — R$ 100,00 | 20 TON",     callback_data="plan_anual")],
        [InlineKeyboardButton("🏠 Início",                          callback_data="home")],
    ]
    await query.edit_message_caption(
        caption=(
            "💎 <b>ÁREA VIP — ESCOLHA SEU PLANO</b>\n\n"
            "🎁 <b>3 dias grátis</b> para novos usuários!\n\n"
            "Selecione um plano para ver as formas de pagamento:"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML,
    )

# ─────────────────────────────────────────────
# PLANO — ESCOLHA DO MÉTODO DE PAGAMENTO
# ─────────────────────────────────────────────
async def plan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query     = update.callback_query
    await query.answer()
    plano_key = query.data.split("_")[1]
    plano     = PLANOS[plano_key]

    keyboard = []
    # PIX automático (se configurado)
    if MP_ACCESS_TOKEN:
        keyboard.append([InlineKeyboardButton(
            f"💳 PIX Automático — R$ {plano['valor_brl']:.2f}",
            callback_data=f"pixmp_{plano_key}",
        )])
    # TON automático via Tonkeeper
    keyboard.append([InlineKeyboardButton(
        f"💎 TON via Tonkeeper — {plano['valor_ton']} TON",
        callback_data=f"tonpay_{plano_key}",
    )])
    keyboard.append([InlineKeyboardButton("⬅️ Voltar", callback_data="vip")])

    await query.edit_message_caption(
        caption=(
            f"💎 <b>PLANO {plano['nome'].upper()}</b>\n\n"
            f"📅 Duração: <b>{plano['dias']} dias</b>\n"
            f"💰 PIX: <b>R$ {plano['valor_brl']:.2f}</b>\n"
            f"💎 TON: <b>{plano['valor_ton']} TON</b>\n\n"
            "Escolha a forma de pagamento:"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML,
    )

# ─────────────────────────────────────────────
# PIX — HANDLER DE GERAÇÃO
# ─────────────────────────────────────────────
async def pixmp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query     = update.callback_query
    await query.answer("Gerando PIX... aguarde ⏳")
    plano_key = query.data.split("_")[1]
    plano     = PLANOS[plano_key]
    user_id   = str(query.from_user.id)

    await query.edit_message_caption(
        caption=f"⏳ <b>Gerando PIX...</b>\n\nPlano: <b>{plano['nome']}</b> — R$ {plano['valor_brl']:.2f}",
        parse_mode=ParseMode.HTML,
    )

    pix_data = await criar_pix_mp(plano_key, user_id)

    if not pix_data:
        await query.edit_message_caption(
            caption="❌ <b>Erro ao gerar PIX.</b>\n\nTente novamente ou escolha TON.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Voltar", callback_data=f"plan_{plano_key}")]]),
            parse_mode=ParseMode.HTML,
        )
        return

    salvar_pagamento(pix_data)
    qr_code  = pix_data["qr_code"]
    qr_b64   = pix_data["qr_base64"]
    pay_id   = pix_data["payment_id"]

    caption_pix = (
        f"✅ <b>PIX gerado!</b>\n\n"
        f"💎 Plano: <b>{plano['nome']}</b> | R$ <b>{plano['valor_brl']:.2f}</b>\n\n"
        f"📋 <b>Copia e Cola:</b>\n<code>{qr_code}</code>\n\n"
        f"⏰ Expira em <b>{PIX_EXPIRY_MINUTES} minutos</b>\n\n"
        "✅ VIP ativado <b>automaticamente</b> após o pagamento!"
    )
    keyboard = [[InlineKeyboardButton("🏠 Voltar ao Início", callback_data="home")]]

    try:
        if qr_b64:
            import base64, io
            img_bytes = base64.b64decode(qr_b64)
            await context.bot.send_photo(
                chat_id=int(user_id), photo=io.BytesIO(img_bytes),
                caption=caption_pix,
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML,
            )
        else:
            await context.bot.send_message(
                chat_id=int(user_id), text=caption_pix,
                reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML,
            )
    except Exception as e:
        logger.error(f"Erro ao enviar QR PIX: {e}")
        await query.edit_message_caption(
            caption=caption_pix,
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML,
        )

    asyncio.create_task(monitorar_pix(pay_id, user_id, plano_key, context))
    logger.info(f"Monitorando PIX {pay_id} — user {user_id}")

# ─────────────────────────────────────────────
# TON — HANDLER DE GERAÇÃO
# ─────────────────────────────────────────────
async def tonpay_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gera instrução de pagamento TON com código de referência único."""
    query     = update.callback_query
    await query.answer()
    plano_key = query.data.split("_")[1]
    plano     = PLANOS[plano_key]
    user_id   = str(query.from_user.id)

    referencia  = gerar_referencia_ton(user_id, plano_key)
    nanotons    = int(plano["valor_ton"] * 1e9)
    tk_url      = tonkeeper_url(TON_ADDRESS, nanotons, referencia)

    # Salva pendente
    salvar_pagamento({
        "type":       "ton",
        "referencia": referencia,
        "plano":      plano_key,
        "user_id":    user_id,
        "created_at": datetime.now().isoformat(),
    })

    caption = (
        f"💎 <b>PAGAMENTO TON</b>\n\n"
        f"📅 Plano: <b>{plano['nome']}</b>\n"
        f"💰 Valor: <b>{plano['valor_ton']} TON</b>\n\n"
        f"👛 <b>Carteira:</b>\n<code>{TON_ADDRESS}</code>\n\n"
        f"🔑 <b>Código de referência (MEMO obrigatório):</b>\n"
        f"<code>{referencia}</code>\n\n"
        "⚠️ <b>Importante:</b> inclua o código acima no campo <b>Memo/Comentário</b> do Tonkeeper!\n\n"
        f"⏰ Expira em <b>{TON_EXPIRY_MINUTES} minutos</b>\n\n"
        "✅ VIP ativado <b>automaticamente</b> após a confirmação na blockchain!"
    )
    keyboard = [
        [InlineKeyboardButton("💎 Abrir Tonkeeper", url=tk_url)],
        [InlineKeyboardButton("🏠 Voltar ao Início", callback_data="home")],
    ]

    try:
        await context.bot.send_message(
            chat_id=int(user_id), text=caption,
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        await query.edit_message_caption(
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML,
        )

    asyncio.create_task(monitorar_ton(referencia, user_id, plano_key, context))
    logger.info(f"Monitorando TON ref={referencia} — user {user_id}")

# ─────────────────────────────────────────────
# COMANDOS ADMIN
# ─────────────────────────────────────────────
async def addlink_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_ID): return
    if len(context.args) < 2:
        await update.message.reply_text("Uso: /addlink <chave> <url>\nEx: /addlink d1_1 https://site.com/ep1")
        return
    key, url = context.args[0], context.args[1]
    db = load_json(VIDEO_DB); db[key] = url; save_json(VIDEO_DB, db)
    await update.message.reply_text(f"✅ Link salvo!\n<code>{key}</code> → {url}", parse_mode=ParseMode.HTML)

async def addvip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_ID): return
    if not context.args:
        await update.message.reply_text("Uso: /addvip <user_id> [dias]"); return
    uid  = context.args[0]
    dias = int(context.args[1]) if len(context.args) > 1 else 30
    activate_vip(uid, dias)
    msg = "♾️ VIP Vitalício" if dias >= 36000 else f"💎 VIP por {dias} dias"
    await update.message.reply_text(f"✅ {msg} para <code>{uid}</code>!", parse_mode=ParseMode.HTML)

async def listusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_ID): return
    users = load_json(DATA_FILE)
    if not users:
        await update.message.reply_text("Nenhum usuário ainda."); return
    lines = [f"👥 <b>Usuários ({len(users)})</b>\n"]
    for uid, data in list(users.items())[:50]:
        status = "💎" if is_vip_active(migrate_user(data)) else "🔒"
        name   = data.get("first_name") or data.get("username") or uid
        lines.append(f"• <code>{uid}</code> ({name}) {status} | 🔗 {data.get('referrals',0)}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

async def setreferrals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_ID): return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            f"ℹ️ Mínimo atual: <b>{get_min_referrals()}</b>\n\nUso: /setreferrals <número>",
            parse_mode=ParseMode.HTML); return
    value = int(context.args[0]); set_min_referrals(value)
    await update.message.reply_text(f"✅ Mínimo atualizado para <b>{value}</b>!", parse_mode=ParseMode.HTML)

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_ID): return
    if not context.args:
        await update.message.reply_text("Uso: /broadcast <mensagem>"); return
    msg_text = " ".join(context.args)
    users    = load_json(DATA_FILE)
    sent = failed = 0
    for uid in users:
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text=f"📢 <b>Mensagem da equipe DORAMAS VIP:</b>\n\n{msg_text}",
                parse_mode=ParseMode.HTML,
            )
            sent += 1; await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    await update.message.reply_text(
        f"✅ Broadcast!\n📤 Enviado: <b>{sent}</b> | ❌ Falhou: <b>{failed}</b>",
        parse_mode=ParseMode.HTML)

async def listpayments_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_ID): return
    payments = load_json(PAYMENTS_FILE)
    if not payments:
        await update.message.reply_text("Nenhum pagamento pendente."); return
    lines = [f"💳 <b>Pendentes ({len(payments)})</b>\n"]
    for key, p in list(payments.items())[:20]:
        tipo    = p.get("type", "?").upper()
        created = p.get("created_at", "")[:16].replace("T", " ")
        lines.append(f"• [{tipo}] <code>{key}</code>\n  👤 {p['user_id']} | {p['plano']} | {created}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /upload <dorama_id> <episodio> <url_ou_file_id>"""
    if str(update.effective_user.id) != str(ADMIN_ID):
        return
    if len(context.args) < 3:
        await update.message.reply_text(
            "Uso: /upload <dorama_id> <episodio> <url>\n"
            "Ex: /upload d1 3 https://site.com/video.mp4\n\n"
            "Doramas disponíveis:\n" +
            "\n".join(f"  <code>{k}</code> — {v['title']}" for k, v in DORAMAS_CATALOG.items()),
            parse_mode=ParseMode.HTML,
        )
        return
    d_id, ep, url = context.args[0], context.args[1], context.args[2]
    if d_id not in DORAMAS_CATALOG:
        await update.message.reply_text(f"Dorama <code>{d_id}</code> nao encontrado.", parse_mode=ParseMode.HTML)
        return
    key = f"{d_id}_{ep}"
    db = load_json(VIDEO_DB)
    db[key] = url
    save_json(VIDEO_DB, db)
    title = DORAMAS_CATALOG[d_id]["title"]
    await update.message.reply_text(
        f"Link salvo!\n\n<b>{title}</b> — Ep {ep}\n<code>{key}</code> -> {url}",
        parse_mode=ParseMode.HTML,
    )

async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /config <chave> <valor>
    Chaves: pix, ton, ad, vip, broadcast
    """
    if str(update.effective_user.id) != str(ADMIN_ID):
        return
    if not context.args:
        await update.message.reply_text(
            "Uso:\n"
            "  /config pix <chave_pix>\n"
            "  /config ton <endereco_ton>\n"
            "  /config ad <texto_do_anuncio>\n"
            "  /config vip <user_id> <dias>\n"
            "  /config broadcast <mensagem>",
            parse_mode=ParseMode.HTML,
        )
        return

    sub = context.args[0].lower()
    rest = context.args[1:]

    if sub == "pix" and rest:
        cfg = load_json(CONFIG_FILE)
        cfg["pix_key"] = rest[0]
        save_json(CONFIG_FILE, cfg)
        await update.message.reply_text(f"Chave PIX atualizada: <code>{rest[0]}</code>", parse_mode=ParseMode.HTML)

    elif sub == "ton" and rest:
        cfg = load_json(CONFIG_FILE)
        cfg["ton_address"] = rest[0]
        save_json(CONFIG_FILE, cfg)
        await update.message.reply_text(f"Endereco TON atualizado: <code>{rest[0]}</code>", parse_mode=ParseMode.HTML)

    elif sub == "ad":
        ad_text = " ".join(rest) if rest else ""
        cfg = load_json(CONFIG_FILE)
        if ad_text:
            cfg["ad_text"] = ad_text
            save_json(CONFIG_FILE, cfg)
            await update.message.reply_text(f"Anuncio configurado: {ad_text}")
        else:
            cfg.pop("ad_text", None)
            save_json(CONFIG_FILE, cfg)
            await update.message.reply_text("Anuncio removido.")

    elif sub == "vip" and len(rest) >= 1:
        uid = rest[0]
        dias = int(rest[1]) if len(rest) > 1 else 30
        activate_vip(uid, dias)
        msg = "VIP Vitalicio" if dias >= 36000 else f"VIP por {dias} dias"
        await update.message.reply_text(f"{msg} para <code>{uid}</code>!", parse_mode=ParseMode.HTML)

    elif sub == "broadcast" and rest:
        msg_text = " ".join(rest)
        users = load_json(DATA_FILE)
        sent = failed = 0
        for uid in users:
            try:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=f"<b>Mensagem da equipe DORAMAS VIP:</b>\n\n{msg_text}",
                    parse_mode=ParseMode.HTML,
                )
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1
        await update.message.reply_text(
            f"Broadcast!\nEnviado: <b>{sent}</b> | Falhou: <b>{failed}</b>",
            parse_mode=ParseMode.HTML,
        )

    else:
        await update.message.reply_text("Parametros invalidos. Use /config sem argumentos para ver o uso.")

async def random_content_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Envia um conteudo aleatorio do catalogo ao usuario VIP."""
    user_data, _, _ = ensure_user(update.effective_user.id)
    if not is_vip_active(user_data):
        await update.message.reply_text(
            "Voce precisa ser VIP para usar este comando.\nUse /start para ver os planos.",
        )
        return
    db = load_json(VIDEO_DB)
    available = {k: v for k, v in db.items() if v and v.strip() not in ("", "COLOQUE_O_FILE_ID_AQUI")}
    if not available:
        await update.message.reply_text("Nenhum conteudo disponivel no momento.")
        return
    key = random.choice(list(available.keys()))
    url = available[key]
    parts = key.split("_")
    d_id, ep = parts[0], parts[1] if len(parts) > 1 else "?"
    title = DORAMAS_CATALOG.get(d_id, {}).get("title", d_id)
    keyboard = [[InlineKeyboardButton(f"Assistir {title} Ep {ep}", url=url)]]
    await update.message.reply_text(
        f"<b>{title}</b> - Episodio {ep}",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
    )

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) == str(ADMIN_ID):
        file_id = update.message.video.file_id
        await update.message.reply_text(
            f"<b>File ID:</b>\n<code>{file_id}</code>\n\n"
            f"Use: /addlink <chave> <code>{file_id}</code>",
            parse_mode=ParseMode.HTML,
        )

# ─────────────────────────────────────────────
# PAINEL ADMIN
# ─────────────────────────────────────────────
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_ID): return
    users    = load_json(DATA_FILE)
    payments = load_json(PAYMENTS_FILE)
    vip_c    = sum(1 for u in users.values() if u.get("is_vip"))
    keyboard = [
        [InlineKeyboardButton("🎁 Dar 3 dias VIP",  callback_data="admin_vip3_ask")],
        [InlineKeyboardButton("👥 Listar Usuários", callback_data="admin_list")],
        [InlineKeyboardButton("📊 Estatísticas",    callback_data="admin_stats")],
    ]
    await update.message.reply_text(
        f"🛠️ <b>PAINEL ADMIN</b>\n\n"
        f"👥 Total: <b>{len(users)}</b> | 💎 VIP: <b>{vip_c}</b>\n"
        f"💳 Pagamentos pendentes: <b>{len(payments)}</b>\n\nEscolha uma ação:",
        reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML,
    )

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if str(query.from_user.id) != str(ADMIN_ID): return
    data = query.data

    if data == "admin_vip3_ask":
        context.user_data["admin_action"] = "vip3"
        await query.edit_message_text(
            "🎁 <b>Ativar 3 dias VIP</b>\n\nEnvie o <b>ID do usuário</b>:", parse_mode=ParseMode.HTML)

    elif data == "admin_list":
        users = load_json(DATA_FILE)
        lines = [f"👥 <b>Usuários ({len(users)})</b>\n"]
        for uid, d in list(users.items())[:30]:
            status = "💎" if d.get("is_vip") else ("🎁" if d.get("trial_expiry") else "🔒")
            name   = d.get("first_name") or d.get("username") or uid
            lines.append(f"• <code>{uid}</code> ({name}) {status} | 🔗 {d.get('referrals',0)}")
        await query.edit_message_text(
            "\n".join(lines), parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Voltar", callback_data="admin_back")]]),
        )

    elif data == "admin_stats":
        users    = load_json(DATA_FILE)
        payments = load_json(PAYMENTS_FILE)
        vip_c    = sum(1 for u in users.values() if u.get("is_vip"))
        trial_c  = sum(1 for u in users.values()
                       if u.get("trial_expiry") and datetime.fromisoformat(u["trial_expiry"]) > datetime.now())
        ref_c    = sum(1 for u in users.values() if u.get("referral_unlocked"))
        pix_c    = sum(1 for p in payments.values() if p.get("type") == "pix")
        ton_c    = sum(1 for p in payments.values() if p.get("type") == "ton")
        await query.edit_message_text(
            f"📊 <b>ESTATÍSTICAS</b>\n\n"
            f"👥 Total: <b>{len(users)}</b>\n💎 VIP: <b>{vip_c}</b>\n"
            f"🎁 Trial: <b>{trial_c}</b>\n🔗 Convites: <b>{ref_c}</b>\n\n"
            f"💳 PIX pendentes: <b>{pix_c}</b>\n💎 TON pendentes: <b>{ton_c}</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("⬅️ Voltar", callback_data="admin_back")]]),
        )

    elif data == "admin_back":
        users    = load_json(DATA_FILE)
        payments = load_json(PAYMENTS_FILE)
        vip_c    = sum(1 for u in users.values() if u.get("is_vip"))
        keyboard = [
            [InlineKeyboardButton("🎁 Dar 3 dias VIP",  callback_data="admin_vip3_ask")],
            [InlineKeyboardButton("👥 Listar Usuários", callback_data="admin_list")],
            [InlineKeyboardButton("📊 Estatísticas",    callback_data="admin_stats")],
        ]
        await query.edit_message_text(
            f"🛠️ <b>PAINEL ADMIN</b>\n\n"
            f"👥 Total: <b>{len(users)}</b> | 💎 VIP: <b>{vip_c}</b>\n"
            f"💳 Pagamentos pendentes: <b>{len(payments)}</b>\n\nEscolha uma ação:",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.HTML,
        )

async def admin_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_ID): return
    action = context.user_data.get("admin_action")
    if not action: return
    text = update.message.text.strip()

    if action == "vip3":
        context.user_data.pop("admin_action", None)
        if not text.lstrip("-").isdigit():
            await update.message.reply_text("❌ ID inválido. Use /admin."); return
        uid = text; activate_vip(uid, 3)
        try:
            await context.bot.send_message(
                chat_id=int(uid),
                text="🎉 <b>Parabéns!</b>\n\n💎 Você recebeu <b>3 dias de VIP</b> gratuito! 🍿",
                parse_mode=ParseMode.HTML)
            notif = "✅ Usuário notificado."
        except Exception:
            notif = "⚠️ Não foi possível notificar."
        await update.message.reply_text(
            f"✅ <b>3 dias VIP ativados!</b>\n👤 <code>{uid}</code>\n\n{notif}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🛠️ Painel", callback_data="admin_back")]]),
            parse_mode=ParseMode.HTML,
        )

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
async def post_init(app) -> None:
    """Configura os comandos do menu do Telegram."""
    try:
        await app.bot.set_my_commands([
            BotCommand("start", "Menu principal"),
            BotCommand("status", "Ver meu status VIP"),
        ])
    except Exception as e:
        logger.warning(f"Nao foi possivel definir comandos do bot: {e}")

def build_app():
    app = ApplicationBuilder().token(TOKEN).build()
    app.post_init = post_init
    app.add_handler(CommandHandler("start",         start))
    app.add_handler(CommandHandler("addlink",       addlink_command))
    app.add_handler(CommandHandler("addvip",        addvip_command))
    app.add_handler(CommandHandler("upload",        upload_command))
    app.add_handler(CommandHandler("config",        config_command))
    app.add_handler(CommandHandler("listusers",     listusers_command))
    app.add_handler(CommandHandler("setreferrals",  setreferrals_command))
    app.add_handler(CommandHandler("broadcast",     broadcast_command))
    app.add_handler(CommandHandler("listpayments",  listpayments_command))
    app.add_handler(CommandHandler("random",        random_content_command))
    app.add_handler(CommandHandler("admin",         admin_panel))
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern=r"^admin_"))
    app.add_handler(CallbackQueryHandler(referral_handler,       pattern=r"^referral$"))
    app.add_handler(CallbackQueryHandler(catalog_handler,        pattern=r"^cat_"))
    app.add_handler(CallbackQueryHandler(view_handler,           pattern=r"^view_"))
    app.add_handler(CallbackQueryHandler(play_handler,           pattern=r"^play_"))
    app.add_handler(CallbackQueryHandler(vip_handler,            pattern=r"^vip$"))
    app.add_handler(CallbackQueryHandler(plan_handler,           pattern=r"^plan_"))
    app.add_handler(CallbackQueryHandler(pixmp_handler,          pattern=r"^pixmp_"))
    app.add_handler(CallbackQueryHandler(tonpay_handler,         pattern=r"^tonpay_"))
    app.add_handler(CallbackQueryHandler(status_handler,         pattern=r"^status$"))
    app.add_handler(CallbackQueryHandler(start,                  pattern=r"^home$"))
    app.add_handler(MessageHandler(filters.VIDEO,                 handle_video))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_message_handler))
    return app

async def run_bot():
    app = build_app()
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True, poll_interval=1.0)
        logger.info("🚀 Bot Online — PIX + TON automáticos ativos!")
        while True:
            await asyncio.sleep(3600)

def main():
    while True:
        try:
            asyncio.run(run_bot())
        except (KeyboardInterrupt, SystemExit):
            logger.info("Bot encerrado."); break
        except Exception as e:
            logger.error(f"⚠️ Erro: {e}. Reconectando em 5s...")
            time.sleep(5)

if __name__ == "__main__":
    main()
