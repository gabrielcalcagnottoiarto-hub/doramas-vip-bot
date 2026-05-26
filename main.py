import logging
import sqlite3
import os
import asyncio
import time
import subprocess
import shutil
import tempfile
import threading
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta

import httpx
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
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# CONFIGURACOES (variaveis de ambiente)
# ─────────────────────────────────────────────
TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = os.environ.get("ADMIN_ID", "")
MP_ACCESS_TOKEN = os.environ.get("MP_ACCESS_TOKEN", "")
TONCENTER_KEY = os.environ.get("TONCENTER_KEY", "")
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

TON_ADDRESS = os.environ.get(
    "TON_ADDRESS", "UQDn8qu6wduopti68NN9aFjJ0ORN8diPtuUMuR8_7tQG7lai"
)
PIX_KEY_DEFAULT = os.environ.get("PIX_KEY", "")

DB_NAME = os.environ.get("DB_NAME", "bot.db")

PLANOS = {
    "mensal": {"nome": "Mensal", "valor_brl": 15.00, "valor_ton": 3.0, "dias": 30},
    "trimestral": {
        "nome": "Trimestral",
        "valor_brl": 35.00,
        "valor_ton": 7.0,
        "dias": 90,
    },
    "anual": {"nome": "Anual", "valor_brl": 100.00, "valor_ton": 20.0, "dias": 365},
}

TRIAL_DAYS = 3
MIN_REFERRALS_DEFAULT = 5
REFERRAL_DAYS = 30
PIX_EXPIRY_MINUTES = 30
PIX_CHECK_INTERVAL = 20
TON_EXPIRY_MINUTES = 30
TON_CHECK_INTERVAL = 30
TON_TOLERANCE = 0.01

WELCOME_IMAGE_URL = os.environ.get(
    "WELCOME_IMAGE_URL",
    "https://img.freepik.com/vetores-premium/"
    "ilustracao-de-estilo-anime-de-um-casal-em-um-encontro-romantico_23-2148817840.jpg",
)

# Diretorio de videos locais
VIDEO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "videos")
VIDEO_DIR_HD = os.path.join(VIDEO_DIR, "hd")
VIDEO_DIR_SD = os.path.join(VIDEO_DIR, "sd")
for _d in [VIDEO_DIR, VIDEO_DIR_HD, VIDEO_DIR_SD]:
    os.makedirs(_d, exist_ok=True)


# ─────────────────────────────────────────────
# BANCO DE DADOS (SQLite)
# ─────────────────────────────────────────────
def db_query(query, params=(), fetchone=False, fetchall=False):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(query, params)
        if fetchone:
            res = cursor.fetchone()
        elif fetchall:
            res = cursor.fetchall()
        else:
            res = None
        conn.commit()
        conn.close()
        return res
    except Exception as e:
        logger.error(f"Erro no banco de dados: {e}")
        return None


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT DEFAULT '',
        first_name TEXT DEFAULT '',
        is_vip BOOLEAN DEFAULT 0,
        vip_expiry TEXT,
        trial_expiry TEXT,
        test_used BOOLEAN DEFAULT 0,
        referred_by TEXT,
        referrals INTEGER DEFAULT 0,
        referral_unlocked BOOLEAN DEFAULT 0,
        referral_unlock_expiry TEXT,
        joined_at TEXT DEFAULT CURRENT_TIMESTAMP
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        file_id TEXT,
        file_id_low TEXT,
        url TEXT,
        url_low TEXT,
        thumbnail_url TEXT,
        price REAL DEFAULT 0,
        category TEXT DEFAULT 'geral',
        is_vip_content BOOLEAN DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS payments (
        id TEXT PRIMARY KEY,
        type TEXT,
        user_id TEXT,
        plano TEXT,
        referencia TEXT,
        created_at TEXT
    )"""
    )
    # Migracao segura
    for col, ctype in [
        ("file_id_low", "TEXT"),
        ("url", "TEXT"),
        ("url_low", "TEXT"),
        ("thumbnail_url", "TEXT"),
    ]:
        try:
            c.execute(f"ALTER TABLE videos ADD COLUMN {col} {ctype}")
        except Exception:
            pass
    for col, ctype in [
        ("trial_expiry", "TEXT"),
        ("referred_by", "TEXT"),
        ("referrals", "INTEGER DEFAULT 0"),
        ("referral_unlocked", "BOOLEAN DEFAULT 0"),
        ("referral_unlock_expiry", "TEXT"),
        ("first_name", "TEXT DEFAULT ''"),
    ]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} {ctype}")
        except Exception:
            pass
    conn.commit()
    conn.close()
    logger.info("Banco de dados inicializado.")


# ─────────────────────────────────────────────
# CONFIG helpers
# ─────────────────────────────────────────────
def get_config(key, default=""):
    row = db_query("SELECT value FROM config WHERE key = ?", (key,), fetchone=True)
    return row[0] if row else default


def set_config(key, value):
    db_query(
        "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, str(value))
    )


def get_pix_key():
    return get_config("pix_key", PIX_KEY_DEFAULT)


def get_min_referrals():
    val = get_config("min_referrals", "")
    return int(val) if val else MIN_REFERRALS_DEFAULT


def get_ad_text():
    ad = get_config("ad_text", "")
    return ad if ad else "Quer conteudo em HD sem propagandas? Assine VIP! Use /start"


# ─────────────────────────────────────────────
# USUARIOS
# ─────────────────────────────────────────────
def ensure_user(user_id, referred_by=None, first_name="", username=""):
    uid = int(user_id)
    existing = db_query(
        "SELECT user_id FROM users WHERE user_id = ?", (uid,), fetchone=True
    )
    notif_ref_id = None
    notif_ref_data = None

    if not existing:
        trial_expiry = (datetime.now() + timedelta(days=TRIAL_DAYS)).isoformat()
        db_query(
            """INSERT INTO users (user_id, username, first_name, trial_expiry, referred_by)
               VALUES (?, ?, ?, ?, ?)""",
            (uid, username, first_name, trial_expiry, referred_by),
        )
        logger.info(f"Novo usuario {uid} — trial ate {trial_expiry}")

        if referred_by and str(referred_by) != str(uid):
            ref_id = int(referred_by)
            db_query(
                "UPDATE users SET referrals = referrals + 1 WHERE user_id = ?",
                (ref_id,),
            )
            ref_user = db_query(
                "SELECT referrals, referral_unlocked FROM users WHERE user_id = ?",
                (ref_id,),
                fetchone=True,
            )
            if ref_user:
                ref_count, ref_unlocked = ref_user
                min_ref = get_min_referrals()
                if ref_count >= min_ref and not ref_unlocked:
                    unlock_expiry = (
                        datetime.now() + timedelta(days=REFERRAL_DAYS)
                    ).isoformat()
                    db_query(
                        "UPDATE users SET referral_unlocked = 1, referral_unlock_expiry = ? WHERE user_id = ?",
                        (unlock_expiry, ref_id),
                    )
                notif_ref_id = str(ref_id)
                notif_ref_data = db_query(
                    "SELECT referrals, referral_unlocked, referral_unlock_expiry FROM users WHERE user_id = ?",
                    (ref_id,),
                    fetchone=True,
                )
    else:
        if first_name or username:
            db_query(
                "UPDATE users SET first_name = COALESCE(NULLIF(?, ''), first_name), username = COALESCE(NULLIF(?, ''), username) WHERE user_id = ?",
                (first_name, username, uid),
            )

    user_data = db_query(
        "SELECT * FROM users WHERE user_id = ?", (uid,), fetchone=True
    )
    return user_data, notif_ref_id, notif_ref_data


def _user_dict(row):
    if not row:
        return {}
    cols = [
        "user_id",
        "username",
        "first_name",
        "is_vip",
        "vip_expiry",
        "trial_expiry",
        "test_used",
        "referred_by",
        "referrals",
        "referral_unlocked",
        "referral_unlock_expiry",
        "joined_at",
    ]
    return dict(zip(cols, row))


def is_vip_active(user_id):
    row = db_query(
        "SELECT is_vip, vip_expiry, trial_expiry, referral_unlocked, referral_unlock_expiry FROM users WHERE user_id = ?",
        (int(user_id),),
        fetchone=True,
    )
    if not row:
        return False
    is_vip, vip_expiry, trial_expiry, ref_unlocked, ref_unlock_expiry = row
    if is_vip:
        if vip_expiry is None:
            return True
        try:
            if datetime.fromisoformat(vip_expiry) > datetime.now():
                return True
        except Exception:
            pass
    if trial_expiry:
        try:
            if datetime.fromisoformat(trial_expiry) > datetime.now():
                return True
        except Exception:
            pass
    if ref_unlocked:
        if ref_unlock_expiry is None:
            return True
        try:
            if datetime.fromisoformat(ref_unlock_expiry) > datetime.now():
                return True
        except Exception:
            pass
    return False


def vip_status_text(user_id):
    row = db_query(
        "SELECT is_vip, vip_expiry, trial_expiry, referral_unlocked, referral_unlock_expiry FROM users WHERE user_id = ?",
        (int(user_id),),
        fetchone=True,
    )
    if not row:
        return "Sem acesso ativo"
    is_vip, vip_expiry, trial_expiry, ref_unlocked, ref_unlock_expiry = row
    if trial_expiry:
        try:
            t_dt = datetime.fromisoformat(trial_expiry)
            if t_dt > datetime.now():
                days_left = (t_dt - datetime.now()).days + 1
                return f"<b>Trial gratis</b> — {days_left} dia(s) restante(s)"
        except Exception:
            pass
    if is_vip:
        if vip_expiry is None:
            return "<b>VIP Vitalicio</b>"
        try:
            exp_dt = datetime.fromisoformat(vip_expiry)
            if exp_dt > datetime.now():
                days_left = (exp_dt - datetime.now()).days + 1
                return f"<b>VIP ativo</b> — expira em {days_left} dia(s)"
        except Exception:
            pass
    if ref_unlocked:
        if ref_unlock_expiry:
            try:
                ref_dt = datetime.fromisoformat(ref_unlock_expiry)
                if ref_dt > datetime.now():
                    days_left = (ref_dt - datetime.now()).days + 1
                    return f"<b>Acesso por convites</b> — {days_left} dia(s)"
            except Exception:
                pass
        else:
            return "<b>Acesso desbloqueado por referencias!</b>"
    return "<b>Sem acesso ativo</b> — assine o VIP ou convide amigos!"


def activate_vip(user_id, dias):
    uid = int(user_id)
    db_query(
        "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (uid,)
    )
    if dias >= 36000:
        db_query(
            "UPDATE users SET is_vip = 1, vip_expiry = NULL WHERE user_id = ?", (uid,)
        )
    else:
        expiry = (datetime.now() + timedelta(days=dias)).isoformat()
        db_query(
            "UPDATE users SET is_vip = 1, vip_expiry = ? WHERE user_id = ?",
            (expiry, uid),
        )


# ─────────────────────────────────────────────
# REFERENCIAS
# ─────────────────────────────────────────────
def get_referral_link(bot_username, user_id):
    return f"https://t.me/{bot_username}?start=ref_{user_id}"


def referral_progress_text(user_id):
    row = db_query(
        "SELECT referrals, referral_unlocked, referral_unlock_expiry FROM users WHERE user_id = ?",
        (int(user_id),),
        fetchone=True,
    )
    if not row:
        return ""
    referrals, ref_unlocked, ref_unlock_expiry = row
    min_ref = get_min_referrals()
    if ref_unlocked:
        if ref_unlock_expiry:
            try:
                ref_dt = datetime.fromisoformat(ref_unlock_expiry)
                remaining = max((ref_dt - datetime.now()).days + 1, 0)
                if ref_dt <= datetime.now():
                    return f"Acesso por convites expirado.\nConvide mais {min_ref} pessoas ou assine o VIP!"
                return (
                    f"Acesso liberado por convites!\n"
                    f"Voce convidou <b>{referrals}</b> pessoa(s)\n"
                    f"Expira em <b>{remaining} dia(s)</b>"
                )
            except Exception:
                pass
        return f"Acesso liberado por convites!\nVoce convidou <b>{referrals}</b> pessoa(s)"
    remaining = min_ref - referrals
    bar_filled = int((referrals / min_ref) * 10) if min_ref > 0 else 0
    bar = "🟩" * bar_filled + "⬜" * (10 - bar_filled)
    return (
        f"<b>Seu Progresso de Convites</b>\n\n{bar}\n"
        f"<b>{referrals} / {min_ref}</b> pessoas convidadas\n\n"
        f"Faltam <b>{remaining}</b> convite(s) para desbloquear o acesso gratuito!"
    )


# ─────────────────────────────────────────────
# COMPRESSAO DE VIDEO (ffmpeg)
# ─────────────────────────────────────────────
def compress_video(input_path, output_path, quality="low"):
    try:
        if quality == "low":
            cmd = [
                "ffmpeg", "-i", input_path,
                "-c:v", "libx264", "-preset", "fast",
                "-crf", "32", "-vf", "scale=-2:480",
                "-c:a", "aac", "-b:a", "64k",
                "-movflags", "+faststart",
                "-y", output_path,
            ]
        else:
            cmd = [
                "ffmpeg", "-i", input_path,
                "-c:v", "libx264", "-preset", "slow",
                "-crf", "23", "-vf", "scale=-2:720",
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                "-y", output_path,
            ]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode == 0 and os.path.exists(output_path):
            return True
        logger.error(f"ffmpeg erro: {result.stderr.decode()[:200]}")
        return False
    except subprocess.TimeoutExpired:
        logger.error("ffmpeg timeout (5 min)")
        return False
    except Exception as e:
        logger.error(f"Erro na compressao: {e}")
        return False


async def download_video_from_url(url, dest_path):
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                with open(dest_path, "wb") as f:
                    f.write(resp.content)
                return True
    except Exception as e:
        logger.error(f"Erro ao baixar video: {e}")
    return False


async def send_video_smart(bot, chat_id, vid_row, is_vip_user):
    vid_id, title, description, file_id, file_id_low, url, url_low = (
        vid_row[0],
        vid_row[1],
        vid_row[2],
        vid_row[3],
        vid_row[4],
        vid_row[5],
        vid_row[6],
    )
    ad = get_ad_text()

    if is_vip_user:
        if file_id:
            try:
                await bot.send_video(
                    chat_id=chat_id,
                    video=file_id,
                    caption=f"<b>{title}</b> (HD)\n\n{description}",
                    parse_mode=ParseMode.HTML,
                )
                return True
            except Exception:
                pass
        if url:
            with tempfile.TemporaryDirectory() as tmpdir:
                raw = os.path.join(tmpdir, "raw.mp4")
                out = os.path.join(tmpdir, "hd.mp4")
                if await download_video_from_url(url, raw):
                    compressed = await asyncio.to_thread(
                        compress_video, raw, out, "medium"
                    )
                    send_path = out if compressed else raw
                    try:
                        with open(send_path, "rb") as vf:
                            sent = await bot.send_video(
                                chat_id=chat_id,
                                video=vf,
                                caption=f"<b>{title}</b> (HD)\n\n{description}",
                                parse_mode=ParseMode.HTML,
                            )
                            if sent.video:
                                db_query(
                                    "UPDATE videos SET file_id = ? WHERE id = ?",
                                    (sent.video.file_id, vid_id),
                                )
                        return True
                    except Exception as e:
                        logger.error(f"Erro ao enviar video comprimido: {e}")
            await bot.send_message(
                chat_id=chat_id,
                text=f"<b>{title}</b> (HD)\n\n{description}\n\nDownload: {url}",
                parse_mode=ParseMode.HTML,
            )
            return True
    else:
        caption_free = f"<b>{title}</b> (SD)\n\n{description}\n\n{ad}"
        if file_id_low:
            try:
                await bot.send_video(
                    chat_id=chat_id,
                    video=file_id_low,
                    caption=caption_free,
                    parse_mode=ParseMode.HTML,
                )
                return True
            except Exception:
                pass
        if file_id:
            try:
                await bot.send_video(
                    chat_id=chat_id,
                    video=file_id,
                    caption=caption_free,
                    parse_mode=ParseMode.HTML,
                )
                return True
            except Exception:
                pass
        video_url = url_low or url
        if video_url:
            with tempfile.TemporaryDirectory() as tmpdir:
                raw = os.path.join(tmpdir, "raw.mp4")
                out = os.path.join(tmpdir, "sd.mp4")
                if await download_video_from_url(video_url, raw):
                    compressed = await asyncio.to_thread(
                        compress_video, raw, out, "low"
                    )
                    send_path = out if compressed else raw
                    try:
                        with open(send_path, "rb") as vf:
                            sent = await bot.send_video(
                                chat_id=chat_id,
                                video=vf,
                                caption=caption_free,
                                parse_mode=ParseMode.HTML,
                            )
                            if sent.video:
                                col = "file_id_low" if compressed else "file_id"
                                db_query(
                                    f"UPDATE videos SET {col} = ? WHERE id = ?",
                                    (sent.video.file_id, vid_id),
                                )
                        return True
                    except Exception as e:
                        logger.error(f"Erro ao enviar video comprimido: {e}")
            await bot.send_message(
                chat_id=chat_id,
                text=f"<b>{title}</b> (SD)\n\n{description}\n\nDownload: {video_url}\n\n{ad}",
                parse_mode=ParseMode.HTML,
            )
            return True
    return False


# ─────────────────────────────────────────────
# MERCADO PAGO — PIX AUTOMATICO
# ─────────────────────────────────────────────
async def criar_pix_mp(plano_key, user_id):
    if not MP_ACCESS_TOKEN:
        return None
    plano = PLANOS[plano_key]
    payload = {
        "transaction_amount": plano["valor_brl"],
        "description": f"VIP Bot — Plano {plano['nome']}",
        "payment_method_id": "pix",
        "payer": {"email": f"user{user_id}@vipbot.com"},
        "metadata": {"user_id": user_id, "plano": plano_key},
        "date_of_expiration": (
            datetime.now() + timedelta(minutes=PIX_EXPIRY_MINUTES)
        ).strftime("%Y-%m-%dT%H:%M:%S.000-03:00"),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.mercadopago.com/v1/payments",
                json=payload,
                headers={
                    "Authorization": f"Bearer {MP_ACCESS_TOKEN}",
                    "Content-Type": "application/json",
                    "X-Idempotency-Key": f"vip-{user_id}-{plano_key}-{int(time.time())}",
                },
            )
        data = resp.json()
        if resp.status_code in (200, 201):
            tid = data["point_of_interaction"]["transaction_data"]
            pay_id = str(data["id"])
            db_query(
                "INSERT OR REPLACE INTO payments (id, type, user_id, plano, created_at) VALUES (?, ?, ?, ?, ?)",
                (pay_id, "pix", user_id, plano_key, datetime.now().isoformat()),
            )
            return {
                "type": "pix",
                "payment_id": pay_id,
                "qr_code": tid.get("qr_code", ""),
                "qr_base64": tid.get("qr_code_base64", ""),
                "plano": plano_key,
                "user_id": user_id,
            }
        logger.error(f"MP erro {resp.status_code}: {data}")
    except Exception as e:
        logger.error(f"Erro ao criar PIX MP: {e}")
    return None


async def verificar_pagamento_mp(payment_id):
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
# TON — PAGAMENTO AUTOMATICO
# ─────────────────────────────────────────────
def gerar_referencia_ton(user_id, plano_key):
    ts = int(time.time()) % 100000
    return f"VIP-{str(user_id)[-4:]}-{plano_key[:3].upper()}-{ts}"


def tonkeeper_url(address, nanotons, memo):
    memo_enc = urllib.parse.quote(memo)
    return f"https://app.tonkeeper.com/transfer/{address}?amount={nanotons}&text={memo_enc}"


async def verificar_pagamento_ton(referencia, valor_ton):
    url = "https://toncenter.com/api/v2/getTransactions"
    params = {"address": TON_ADDRESS, "limit": 30, "to_lt": 0}
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
            value = int(in_msg.get("value", 0))
            if referencia in msg_text and abs(value - valor_nanotons) <= tolerancia_nano:
                logger.info(f"TON pago! ref={referencia} valor={value / 1e9:.4f} TON")
                return True
    except Exception as e:
        logger.warning(f"Erro ao verificar TON: {e}")
    return False


# ─────────────────────────────────────────────
# MONITORES DE PAGAMENTO
# ─────────────────────────────────────────────
async def monitorar_pix(payment_id, user_id, plano_key, context):
    plano = PLANOS[plano_key]
    deadline = datetime.now() + timedelta(minutes=PIX_EXPIRY_MINUTES)
    while datetime.now() < deadline:
        await asyncio.sleep(PIX_CHECK_INTERVAL)
        status = await verificar_pagamento_mp(payment_id)
        logger.info(f"PIX {payment_id} — {status}")
        if status == "approved":
            activate_vip(user_id, plano["dias"])
            db_query("DELETE FROM payments WHERE id = ?", (payment_id,))
            await _notificar_aprovado(context, user_id, plano, "PIX", payment_id)
            return
        if status in ("rejected", "cancelled"):
            db_query("DELETE FROM payments WHERE id = ?", (payment_id,))
            await _notificar_recusado(context, user_id)
            return
    db_query("DELETE FROM payments WHERE id = ?", (payment_id,))
    await _notificar_expirado(context, user_id)


async def monitorar_ton(referencia, user_id, plano_key, context):
    plano = PLANOS[plano_key]
    deadline = datetime.now() + timedelta(minutes=TON_EXPIRY_MINUTES)
    while datetime.now() < deadline:
        await asyncio.sleep(TON_CHECK_INTERVAL)
        pago = await verificar_pagamento_ton(referencia, plano["valor_ton"])
        if pago:
            activate_vip(user_id, plano["dias"])
            db_query("DELETE FROM payments WHERE id = ?", (referencia,))
            await _notificar_aprovado(context, user_id, plano, "TON", referencia)
            return
    db_query("DELETE FROM payments WHERE id = ?", (referencia,))
    await _notificar_expirado(context, user_id)


async def _notificar_aprovado(context, user_id, plano, metodo, ref):
    try:
        await context.bot.send_message(
            chat_id=int(user_id),
            text=(
                f"<b>Pagamento confirmado!</b>\n\n"
                f"Metodo: <b>{metodo}</b>\n"
                f"Plano: <b>{plano['nome']}</b>\n"
                f"Aproveite <b>{plano['dias']} dias</b> de acesso ilimitado!\n\n"
                "Use /start para acessar o catalogo."
            ),
            parse_mode=ParseMode.HTML,
        )
        if ADMIN_ID:
            await context.bot.send_message(
                chat_id=int(ADMIN_ID),
                text=(
                    f"<b>Pagamento aprovado!</b>\n\n"
                    f"User: <code>{user_id}</code>\n"
                    f"Plano: <b>{plano['nome']}</b>\n"
                    f"Metodo: <b>{metodo}</b>\n"
                    f"Ref: <code>{ref}</code>"
                ),
                parse_mode=ParseMode.HTML,
            )
    except Exception as e:
        logger.warning(f"Erro ao notificar aprovacao: {e}")


async def _notificar_recusado(context, user_id):
    try:
        await context.bot.send_message(
            chat_id=int(user_id),
            text="<b>Pagamento nao aprovado.</b>\n\nTente novamente em /start.",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass


async def _notificar_expirado(context, user_id):
    try:
        await context.bot.send_message(
            chat_id=int(user_id),
            text="<b>Pagamento expirado.</b>\n\nGere um novo em /start.",
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass


# ─────────────────────────────────────────────
# HELPERS DE ENVIO
# ─────────────────────────────────────────────
async def send_or_edit_photo(update, context, caption, keyboard):
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


# ─────────────────────────────────────────────
# /start
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
            user.id,
            referred_by=referred_by,
            first_name=user.first_name or "",
            username=user.username or "",
        )
        status = vip_status_text(user.id)

        if notif_ref_id and notif_ref_data:
            min_ref = get_min_referrals()
            ref_count = notif_ref_data[0]
            ref_unlocked = notif_ref_data[1]
            ref_unlock_expiry = notif_ref_data[2]
            new_name = user.first_name or "Alguem"
            if ref_unlocked:
                exp_label = ""
                if ref_unlock_expiry:
                    try:
                        exp_dt = datetime.fromisoformat(ref_unlock_expiry)
                        exp_label = f"\nValido ate {exp_dt.strftime('%d/%m/%Y')}"
                    except Exception:
                        pass
                notif_text = (
                    f"<b>Acesso desbloqueado!</b>\n\n"
                    f"<b>{new_name}</b> entrou pelo seu link.\n"
                    f"{ref_count}/{min_ref} convites — acesso liberado!{exp_label}"
                )
            else:
                notif_text = (
                    f"<b>Novo convite!</b>\n\n"
                    f"<b>{new_name}</b> entrou pelo seu link.\n"
                    f"{ref_count}/{min_ref} — faltam {min_ref - ref_count} convite(s)!"
                )
            try:
                await context.bot.send_message(
                    chat_id=int(notif_ref_id),
                    text=notif_text,
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.warning(f"Nao foi possivel notificar {notif_ref_id}: {e}")

        caption = (
            "<b>BOT VIP</b>\n\n"
            f"{status}\n\n"
            "Novos usuarios ganham <b>3 dias gratis</b> automaticamente!\n"
            "Convide amigos e ganhe acesso gratuito!\n"
            "Assine o VIP para acesso ilimitado\n\n"
            "Escolha uma opcao:"
        )
        keyboard = [
            [InlineKeyboardButton("Catalogo", callback_data="menu_cats")],
            [InlineKeyboardButton("Conteudo Aleatorio", callback_data="random_content")],
            [InlineKeyboardButton("Planos VIP", callback_data="vip")],
            [InlineKeyboardButton("Meu Link de Convite", callback_data="referral")],
            [InlineKeyboardButton("Meu Status", callback_data="status")],
        ]
        await send_or_edit_photo(update, context, caption, keyboard)
    except Exception as e:
        logger.error(f"Erro no start: {e}")


# ─────────────────────────────────────────────
# CATALOGO DINAMICO (por categorias do banco)
# ─────────────────────────────────────────────
async def catalog_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    vip = is_vip_active(uid)

    cats = db_query("SELECT DISTINCT category FROM videos", fetchall=True)
    if not cats:
        kb = [[InlineKeyboardButton("Voltar", callback_data="home")]]
        await query.edit_message_caption(
            caption="<b>Catalogo em atualizacao...</b>\n\nAdmin: use /upload ou /add_url para adicionar conteudo.",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode=ParseMode.HTML,
        )
        return

    keyboard = []
    for c in cats:
        cat_name = c[0]
        count = db_query(
            "SELECT COUNT(*) FROM videos WHERE category = ?",
            (cat_name,),
            fetchone=True,
        )
        n = count[0] if count else 0
        label = f"{cat_name.upper()} ({n})"
        if vip:
            label += " HD"
        keyboard.append(
            [InlineKeyboardButton(label, callback_data=f"cat_{cat_name}")]
        )
    keyboard.append([InlineKeyboardButton("Voltar", callback_data="home")])

    title = "<b>CATALOGO VIP — HD</b>" if vip else "<b>CATALOGO</b>\n\nAssine VIP para HD!"
    await query.edit_message_caption(
        caption=title,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
    )


async def cat_videos_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat = query.data[4:]
    uid = query.from_user.id
    vip = is_vip_active(uid)

    vids = db_query(
        "SELECT id, title FROM videos WHERE category = ?", (cat,), fetchall=True
    )
    if not vids:
        kb = [[InlineKeyboardButton("Voltar", callback_data="menu_cats")]]
        await query.edit_message_caption(
            caption=f"<b>{cat.upper()}</b>\n\nNenhum video nesta categoria.",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode=ParseMode.HTML,
        )
        return

    keyboard = []
    for v in vids:
        label = f"{v[1]}"
        if vip:
            label += " (HD)"
        keyboard.append(
            [InlineKeyboardButton(label, callback_data=f"play_{v[0]}")]
        )
    keyboard.append([InlineKeyboardButton("Voltar", callback_data="menu_cats")])
    await query.edit_message_caption(
        caption=f"<b>{cat.upper()}</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
    )


async def play_video_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    vid_id = query.data.split("_")[1]
    uid = query.from_user.id
    vip = is_vip_active(uid)

    v = db_query(
        "SELECT id, title, description, file_id, file_id_low, url, url_low, is_vip_content FROM videos WHERE id = ?",
        (vid_id,),
        fetchone=True,
    )
    if not v:
        await context.bot.send_message(chat_id=uid, text="Conteudo indisponivel.")
        return

    is_vip_content = v[7]
    if is_vip_content and not vip:
        kb = [
            [InlineKeyboardButton("Planos VIP", callback_data="vip")],
            [InlineKeyboardButton("Voltar", callback_data="menu_cats")],
        ]
        await query.edit_message_caption(
            caption="<b>CONTEUDO VIP</b>\n\nAssine VIP para acessar conteudo em HD!",
            reply_markup=InlineKeyboardMarkup(kb),
            parse_mode=ParseMode.HTML,
        )
        return

    if not vip:
        ad = get_ad_text()
        await context.bot.send_message(
            chat_id=uid,
            text=f"<b>PROPAGANDA:</b>\n\n{ad}\n\nAssine VIP para remover propagandas!",
            parse_mode=ParseMode.HTML,
        )

    sent = await send_video_smart(context.bot, uid, v[:7], vip)
    if not sent:
        await context.bot.send_message(chat_id=uid, text="Conteudo indisponivel no momento.")


# ─────────────────────────────────────────────
# CONTEUDO ALEATORIO
# ─────────────────────────────────────────────
async def random_content_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    vip = is_vip_active(uid)

    if vip:
        v = db_query(
            "SELECT id, title, description, file_id, file_id_low, url, url_low FROM videos ORDER BY RANDOM() LIMIT 1",
            fetchone=True,
        )
    else:
        v = db_query(
            "SELECT id, title, description, file_id, file_id_low, url, url_low FROM videos WHERE is_vip_content = 0 ORDER BY RANDOM() LIMIT 1",
            fetchone=True,
        )

    if v:
        if not vip:
            ad = get_ad_text()
            await context.bot.send_message(
                chat_id=uid,
                text=f"<b>PROPAGANDA:</b> {ad}",
                parse_mode=ParseMode.HTML,
            )
        sent = await send_video_smart(context.bot, uid, v, vip)
        if sent:
            return

    await context.bot.send_message(
        chat_id=uid,
        text="Nenhum conteudo disponivel ainda.\nAdmin: use /upload ou /add_url para adicionar conteudo.",
    )


# ─────────────────────────────────────────────
# BUSCA DE VIDEOS — PEXELS API
# ─────────────────────────────────────────────
async def search_videos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    vip = is_vip_active(uid)

    key = get_config("pexels_api_key", PEXELS_API_KEY)
    if not key:
        await update.message.reply_text(
            "API Pexels nao configurada.\nAdmin: /config pexels <sua_api_key>\nObtenha gratis em: https://www.pexels.com/api/"
        )
        return

    search_query = " ".join(context.args) if context.args else "nature"
    per_page = 5 if vip else 2
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.pexels.com/v1/videos/search?query={search_query}&per_page={per_page}&locale=pt-BR",
                headers={"Authorization": key},
            )
        data = resp.json()
        videos = data.get("videos", [])
        if not videos:
            await update.message.reply_text(f"Nenhum video encontrado para: {search_query}")
            return

        if not vip:
            ad = get_ad_text()
            await update.message.reply_text(
                f"<b>PROPAGANDA:</b> {ad}\n\nAssine VIP para resultados em HD!",
                parse_mode=ParseMode.HTML,
            )

        for v in videos:
            video_url = v.get("url", "")
            user_name = v.get("user", {}).get("name", "Desconhecido")
            duration = v.get("duration", 0)

            if vip:
                hd_link = ""
                for vf in v.get("video_files", []):
                    if vf.get("quality") == "hd":
                        hd_link = vf.get("link", "")
                        break
                if not hd_link and v.get("video_files"):
                    hd_link = v["video_files"][0].get("link", "")
                await update.message.reply_text(
                    f"<b>{user_name}</b> ({duration}s) — HD\nPexels: {video_url}\nDownload HD: {hd_link}",
                    parse_mode=ParseMode.HTML,
                )
            else:
                sd_link = ""
                for vf in v.get("video_files", []):
                    if vf.get("quality") == "sd":
                        sd_link = vf.get("link", "")
                        break
                if not sd_link and v.get("video_files"):
                    sd_link = v["video_files"][0].get("link", "")
                await update.message.reply_text(
                    f"<b>{user_name}</b> ({duration}s) — SD\nPexels: {video_url}\nDownload SD: {sd_link}\n\n<i>Assine VIP para download em HD!</i>",
                    parse_mode=ParseMode.HTML,
                )
    except Exception as e:
        logger.error(f"Erro ao buscar videos Pexels: {e}")
        await update.message.reply_text("Erro ao buscar videos. Tente novamente mais tarde.")


# ─────────────────────────────────────────────
# REFERRAL
# ─────────────────────────────────────────────
async def referral_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    ensure_user(uid)
    bot_username = (await context.bot.get_me()).username
    link = get_referral_link(bot_username, uid)
    progress = referral_progress_text(uid)
    min_ref = get_min_referrals()
    text = (
        f"<b>SEU LINK DE CONVITE</b>\n\n{progress}\n\n"
        f"<b>Compartilhe:</b>\n<code>{link}</code>\n\n"
        f"Ao atingir <b>{min_ref} convite(s)</b> voce desbloqueia acesso gratuito!"
    )
    keyboard = [
        [InlineKeyboardButton("Copiar Link", switch_inline_query=link)],
        [InlineKeyboardButton("Inicio", callback_data="home")],
    ]
    await query.edit_message_caption(
        caption=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
    )


# ─────────────────────────────────────────────
# STATUS
# ─────────────────────────────────────────────
async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    keyboard = [
        [InlineKeyboardButton("Catalogo", callback_data="menu_cats")],
        [InlineKeyboardButton("Meu Link de Convite", callback_data="referral")],
        [InlineKeyboardButton("Assinar VIP", callback_data="vip")],
        [InlineKeyboardButton("Inicio", callback_data="home")],
    ]
    await query.edit_message_caption(
        caption=(
            f"<b>Seu Acesso</b>\n\n"
            f"{vip_status_text(uid)}\n\n"
            f"{referral_progress_text(uid)}"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
    )


# ─────────────────────────────────────────────
# VIP — PLANOS
# ─────────────────────────────────────────────
async def vip_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton(f"Mensal — R$ 15,00 | 3 TON", callback_data="plan_mensal")],
        [InlineKeyboardButton(f"Trimestral — R$ 35,00 | 7 TON", callback_data="plan_trimestral")],
        [InlineKeyboardButton(f"Anual — R$ 100,00 | 20 TON", callback_data="plan_anual")],
        [InlineKeyboardButton("Inicio", callback_data="home")],
    ]
    await query.edit_message_caption(
        caption=(
            "<b>AREA VIP — ESCOLHA SEU PLANO</b>\n\n"
            "Novos usuarios ganham <b>3 dias gratis</b>!\n\n"
            "Selecione um plano para ver as formas de pagamento:"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
    )


async def plan_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plano_key = query.data.split("_")[1]
    plano = PLANOS[plano_key]

    keyboard = []
    if MP_ACCESS_TOKEN:
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"PIX Automatico — R$ {plano['valor_brl']:.2f}",
                    callback_data=f"pixmp_{plano_key}",
                )
            ]
        )
    pix_key = get_pix_key()
    if pix_key:
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"PIX Manual — R$ {plano['valor_brl']:.2f}",
                    callback_data=f"pixmanual_{plano_key}",
                )
            ]
        )
    keyboard.append(
        [
            InlineKeyboardButton(
                f"TON via Tonkeeper — {plano['valor_ton']} TON",
                callback_data=f"tonpay_{plano_key}",
            )
        ]
    )
    keyboard.append([InlineKeyboardButton("Voltar", callback_data="vip")])

    await query.edit_message_caption(
        caption=(
            f"<b>PLANO {plano['nome'].upper()}</b>\n\n"
            f"Duracao: <b>{plano['dias']} dias</b>\n"
            f"PIX: <b>R$ {plano['valor_brl']:.2f}</b>\n"
            f"TON: <b>{plano['valor_ton']} TON</b>\n\n"
            "Escolha a forma de pagamento:"
        ),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode=ParseMode.HTML,
    )


async def pixmanual_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plano_key = query.data.split("_")[1]
    plano = PLANOS[plano_key]
    pix_key = get_pix_key()
    txt = (
        f"<b>PAGAMENTO VIA PIX (Manual)</b>\n\n"
        f"Plano: <b>{plano['nome']}</b>\n"
        f"Valor: <b>R$ {plano['valor_brl']:.2f}</b>\n\n"
        f"Chave PIX: <code>{pix_key}</code>\n\n"
        "Envie o comprovante para o admin para ativacao!"
    )
    kb = [[InlineKeyboardButton("Voltar", callback_data=f"plan_{plano_key}")]]
    await query.edit_message_caption(
        caption=txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.HTML
    )


async def pixmp_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Gerando PIX... aguarde")
    plano_key = query.data.split("_")[1]
    plano = PLANOS[plano_key]
    user_id = str(query.from_user.id)

    await query.edit_message_caption(
        caption=f"<b>Gerando PIX...</b>\n\nPlano: <b>{plano['nome']}</b> — R$ {plano['valor_brl']:.2f}",
        parse_mode=ParseMode.HTML,
    )

    pix_data = await criar_pix_mp(plano_key, user_id)
    if not pix_data:
        await query.edit_message_caption(
            caption="<b>Erro ao gerar PIX.</b>\n\nTente novamente ou escolha TON.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Voltar", callback_data=f"plan_{plano_key}")]]
            ),
            parse_mode=ParseMode.HTML,
        )
        return

    qr_code = pix_data["qr_code"]
    qr_b64 = pix_data["qr_base64"]
    pay_id = pix_data["payment_id"]

    caption_pix = (
        f"<b>PIX gerado!</b>\n\n"
        f"Plano: <b>{plano['nome']}</b> | R$ <b>{plano['valor_brl']:.2f}</b>\n\n"
        f"<b>Copia e Cola:</b>\n<code>{qr_code}</code>\n\n"
        f"Expira em <b>{PIX_EXPIRY_MINUTES} minutos</b>\n\n"
        "VIP ativado <b>automaticamente</b> apos o pagamento!"
    )
    keyboard = [[InlineKeyboardButton("Voltar ao Inicio", callback_data="home")]]

    try:
        if qr_b64:
            import base64
            import io

            img_bytes = base64.b64decode(qr_b64)
            await context.bot.send_photo(
                chat_id=int(user_id),
                photo=io.BytesIO(img_bytes),
                caption=caption_pix,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML,
            )
        else:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=caption_pix,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML,
            )
    except Exception as e:
        logger.error(f"Erro ao enviar QR PIX: {e}")
        await query.edit_message_caption(
            caption=caption_pix,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML,
        )

    asyncio.create_task(monitorar_pix(pay_id, user_id, plano_key, context))
    logger.info(f"Monitorando PIX {pay_id} — user {user_id}")


async def tonpay_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plano_key = query.data.split("_")[1]
    plano = PLANOS[plano_key]
    user_id = str(query.from_user.id)

    referencia = gerar_referencia_ton(user_id, plano_key)
    nanotons = int(plano["valor_ton"] * 1e9)
    tk_url = tonkeeper_url(TON_ADDRESS, nanotons, referencia)

    db_query(
        "INSERT OR REPLACE INTO payments (id, type, user_id, plano, referencia, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (referencia, "ton", user_id, plano_key, referencia, datetime.now().isoformat()),
    )

    caption = (
        f"<b>PAGAMENTO TON</b>\n\n"
        f"Plano: <b>{plano['nome']}</b>\n"
        f"Valor: <b>{plano['valor_ton']} TON</b>\n\n"
        f"<b>Carteira:</b>\n<code>{TON_ADDRESS}</code>\n\n"
        f"<b>Codigo de referencia (MEMO obrigatorio):</b>\n"
        f"<code>{referencia}</code>\n\n"
        "<b>Importante:</b> inclua o codigo acima no campo <b>Memo/Comentario</b> do Tonkeeper!\n\n"
        f"Expira em <b>{TON_EXPIRY_MINUTES} minutos</b>\n\n"
        "VIP ativado <b>automaticamente</b> apos a confirmacao na blockchain!"
    )
    keyboard = [
        [InlineKeyboardButton("Abrir Tonkeeper", url=tk_url)],
        [InlineKeyboardButton("Voltar ao Inicio", callback_data="home")],
    ]

    try:
        await context.bot.send_message(
            chat_id=int(user_id),
            text=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        await query.edit_message_caption(
            caption=caption,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.HTML,
        )

    asyncio.create_task(monitorar_ton(referencia, user_id, plano_key, context))
    logger.info(f"Monitorando TON ref={referencia} — user {user_id}")


# ─────────────────────────────────────────────
# COMANDOS ADMIN
# ─────────────────────────────────────────────
def is_admin(user_id):
    return str(user_id) == str(ADMIN_ID)


async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text(
            "Uso: /upload Titulo | Categoria | Preco | sim/nao\n"
            "Envie como resposta a um video.\n\n"
            "Exemplo: /upload Video Top | acao | 0 | sim"
        )
        return
    if not update.message.reply_to_message or not update.message.reply_to_message.video:
        await update.message.reply_text("Responda a um video com o comando /upload.")
        return

    text = " ".join(context.args)
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 4:
        await update.message.reply_text(
            "Formato: /upload Titulo | Categoria | Preco | sim/nao"
        )
        return

    title = parts[0]
    category = parts[1].lower()
    try:
        price = float(parts[2])
    except ValueError:
        price = 0
    is_vip = parts[3].lower() in ("sim", "s", "yes", "y", "1", "true")
    file_id = update.message.reply_to_message.video.file_id

    db_query(
        "INSERT INTO videos (title, description, file_id, price, category, is_vip_content) VALUES (?, ?, ?, ?, ?, ?)",
        (title, "", file_id, price, category, is_vip),
    )
    vid = db_query("SELECT last_insert_rowid()", fetchone=True)
    vid_id = vid[0] if vid else "?"
    vip_label = "SIM" if is_vip else "NAO"
    await update.message.reply_text(
        f"Video salvo (HD)!\n\n"
        f"ID: {vid_id}\n"
        f"Titulo: {title}\n"
        f"Categoria: {category}\n"
        f"Preco: R$ {price:.2f}\n"
        f"VIP: {vip_label}\n\n"
        f"Para adicionar versao baixa resolucao:\n"
        f"Responda a um video SD com: /upload_low {vid_id}"
    )


async def upload_low_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text(
            "Uso: /upload_low <id_do_video>\nResponda a um video em baixa resolucao."
        )
        return
    if not update.message.reply_to_message or not update.message.reply_to_message.video:
        await update.message.reply_text(
            "Responda a um video em baixa resolucao com o comando /upload_low."
        )
        return
    try:
        vid_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID do video invalido.")
        return
    v = db_query("SELECT title FROM videos WHERE id = ?", (vid_id,), fetchone=True)
    if not v:
        await update.message.reply_text(f"Video #{vid_id} nao encontrado.")
        return
    file_id_low = update.message.reply_to_message.video.file_id
    db_query("UPDATE videos SET file_id_low = ? WHERE id = ?", (file_id_low, vid_id))
    await update.message.reply_text(
        f"Versao baixa resolucao salva para: {v[0]} (#{vid_id})\n"
        f"File ID (SD): {file_id_low}"
    )


async def add_url_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text(
            "<b>Adicionar video por URL:</b>\n\n"
            "Formato:\n"
            "/add_url Titulo | Categoria | URL_HD | URL_SD | sim/nao\n\n"
            "Exemplo:\n"
            "/add_url Ensaio | modelo | https://url.com/hd.mp4 | https://url.com/sd.mp4 | sim\n\n"
            "Se nao tiver URL SD, coloque 'nao':\n"
            "/add_url Ensaio | modelo | https://url.com/video.mp4 | nao | sim",
            parse_mode=ParseMode.HTML,
        )
        return

    text = " ".join(context.args)
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 5:
        await update.message.reply_text(
            "Formato incorreto. Use:\n/add_url Titulo | Categoria | URL_HD | URL_SD | sim/nao"
        )
        return

    title = parts[0]
    category = parts[1].lower()
    url_hd = parts[2]
    url_sd = parts[3] if parts[3].lower() not in ("nao", "n", "no", "") else None
    is_vip = parts[4].lower() in ("sim", "s", "yes", "y", "1", "true")

    db_query(
        "INSERT INTO videos (title, description, url, url_low, category, is_vip_content) VALUES (?, ?, ?, ?, ?, ?)",
        (title, "", url_hd, url_sd, category, is_vip),
    )
    vid = db_query("SELECT last_insert_rowid()", fetchone=True)
    vid_id = vid[0] if vid else "?"
    vip_label = "SIM" if is_vip else "NAO"
    sd_label = url_sd if url_sd else "Nao definida"
    await update.message.reply_text(
        f"Video adicionado por URL!\n\n"
        f"ID: {vid_id}\n"
        f"Titulo: {title}\n"
        f"Categoria: {category}\n"
        f"VIP: {vip_label}\n"
        f"URL HD: {url_hd}\n"
        f"URL SD: {sd_label}"
    )


async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text(
            "<b>Comandos de Configuracao:</b>\n\n"
            "  /config pix &lt;chave_pix&gt;\n"
            "  /config vip &lt;user_id&gt; [dias]\n"
            "  /config ad &lt;texto_do_anuncio&gt;\n"
            "  /config broadcast &lt;mensagem&gt;\n"
            "  /config pexels &lt;api_key&gt;\n"
            "  /config referrals &lt;numero_minimo&gt;\n\n"
            "<b>Upload de Videos:</b>\n"
            "  /upload Titulo | Cat | Preco | sim/nao\n"
            "  /upload_low &lt;id_video&gt; (versao SD)\n"
            "  /add_url Titulo | Cat | URL_HD | URL_SD | sim/nao",
            parse_mode=ParseMode.HTML,
        )
        return

    sub = context.args[0].lower()
    rest = context.args[1:]

    if sub == "pix" and rest:
        set_config("pix_key", rest[0])
        await update.message.reply_text(f"Chave PIX atualizada: {rest[0]}")

    elif sub == "vip" and rest:
        try:
            uid = int(rest[0])
        except ValueError:
            await update.message.reply_text("ID do usuario invalido.")
            return
        dias = int(rest[1]) if len(rest) > 1 and rest[1].isdigit() else 30
        activate_vip(uid, dias)
        await update.message.reply_text(f"VIP ativado por {dias} dias para {uid}!")
        try:
            await context.bot.send_message(
                chat_id=uid, text=f"Voce recebeu {dias} dias de VIP!"
            )
        except Exception:
            pass

    elif sub == "ad":
        ad_text = " ".join(rest) if rest else ""
        if ad_text:
            set_config("ad_text", ad_text)
            await update.message.reply_text(f"Anuncio configurado: {ad_text}")
        else:
            db_query("DELETE FROM config WHERE key = ?", ("ad_text",))
            await update.message.reply_text("Anuncio removido.")

    elif sub == "pexels" and rest:
        set_config("pexels_api_key", rest[0])
        await update.message.reply_text("Pexels API Key configurada!")

    elif sub == "referrals" and rest:
        try:
            val = int(rest[0])
            set_config("min_referrals", str(val))
            await update.message.reply_text(f"Minimo de referrals atualizado para {val}!")
        except ValueError:
            await update.message.reply_text("Valor invalido.")

    elif sub == "broadcast" and rest:
        msg_text = " ".join(rest)
        users = db_query("SELECT user_id FROM users", fetchall=True)
        sent = failed = 0
        if users:
            for row in users:
                try:
                    await context.bot.send_message(
                        chat_id=row[0],
                        text=f"<b>Mensagem da equipe:</b>\n\n{msg_text}",
                        parse_mode=ParseMode.HTML,
                    )
                    sent += 1
                    await asyncio.sleep(0.05)
                except Exception:
                    failed += 1
        await update.message.reply_text(
            f"Broadcast!\nEnviado: {sent} | Falhou: {failed}"
        )

    else:
        await update.message.reply_text(
            "Parametros invalidos. Use /config sem argumentos para ver o uso."
        )


async def addvip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Uso: /addvip <user_id> [dias]")
        return
    uid = context.args[0]
    dias = int(context.args[1]) if len(context.args) > 1 else 30
    activate_vip(uid, dias)
    msg = "VIP Vitalicio" if dias >= 36000 else f"VIP por {dias} dias"
    await update.message.reply_text(
        f"{msg} para <code>{uid}</code>!", parse_mode=ParseMode.HTML
    )


async def listusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    users = db_query(
        "SELECT user_id, username, first_name, is_vip, referrals FROM users",
        fetchall=True,
    )
    if not users:
        await update.message.reply_text("Nenhum usuario cadastrado.")
        return
    lines = [f"<b>Usuarios ({len(users)})</b>\n"]
    for u in users[:50]:
        status = "VIP" if u[3] else "FREE"
        name = u[2] or u[1] or str(u[0])
        lines.append(f"<code>{u[0]}</code> ({name}) [{status}] refs: {u[4]}")
    if len(users) > 50:
        lines.append(f"\n... e mais {len(users) - 50} usuarios.")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def listvideos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    vids = db_query(
        "SELECT id, title, category, is_vip_content FROM videos ORDER BY id",
        fetchall=True,
    )
    if not vids:
        await update.message.reply_text("Nenhum video no catalogo.")
        return
    lines = [f"<b>Videos ({len(vids)})</b>\n"]
    for v in vids[:50]:
        vip_tag = "[VIP]" if v[3] else "[FREE]"
        lines.append(f"#{v[0]} — {v[1]} | {v[2]} {vip_tag}")
    if len(vids) > 50:
        lines.append(f"\n... e mais {len(vids) - 50} videos.")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def delvideo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Uso: /delvideo <id>")
        return
    try:
        vid_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID invalido.")
        return
    v = db_query("SELECT title FROM videos WHERE id = ?", (vid_id,), fetchone=True)
    if not v:
        await update.message.reply_text(f"Video #{vid_id} nao encontrado.")
        return
    db_query("DELETE FROM videos WHERE id = ?", (vid_id,))
    await update.message.reply_text(f"Video #{vid_id} ({v[0]}) removido!")


async def listpayments_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    payments = db_query(
        "SELECT id, type, user_id, plano, created_at FROM payments", fetchall=True
    )
    if not payments:
        await update.message.reply_text("Nenhum pagamento pendente.")
        return
    lines = [f"<b>Pagamentos Pendentes ({len(payments)})</b>\n"]
    for p in payments[:20]:
        lines.append(
            f"[{p[1].upper()}] <code>{p[0]}</code>\n  User: {p[2]} | Plano: {p[3]} | {(p[4] or '')[:16]}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Uso: /broadcast <mensagem>")
        return
    msg_text = " ".join(context.args)
    users = db_query("SELECT user_id FROM users", fetchall=True)
    sent = failed = 0
    if users:
        for row in users:
            try:
                await context.bot.send_message(
                    chat_id=row[0],
                    text=f"<b>Mensagem da equipe:</b>\n\n{msg_text}",
                    parse_mode=ParseMode.HTML,
                )
                sent += 1
                await asyncio.sleep(0.05)
            except Exception:
                failed += 1
    await update.message.reply_text(
        f"Broadcast!\nEnviado: {sent} | Falhou: {failed}"
    )


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    total_users = db_query("SELECT COUNT(*) FROM users", fetchone=True)
    vip_users = db_query("SELECT COUNT(*) FROM users WHERE is_vip = 1", fetchone=True)
    total_videos = db_query("SELECT COUNT(*) FROM videos", fetchone=True)
    total_payments = db_query("SELECT COUNT(*) FROM payments", fetchone=True)

    await update.message.reply_text(
        f"<b>PAINEL ADMIN</b>\n\n"
        f"Usuarios: <b>{total_users[0] if total_users else 0}</b>\n"
        f"VIP: <b>{vip_users[0] if vip_users else 0}</b>\n"
        f"Videos: <b>{total_videos[0] if total_videos else 0}</b>\n"
        f"Pagamentos pendentes: <b>{total_payments[0] if total_payments else 0}</b>\n\n"
        "<b>Comandos:</b>\n"
        "/upload — Upload video (responda a video)\n"
        "/upload_low — Upload versao SD\n"
        "/add_url — Adicionar video por URL\n"
        "/addvip — Ativar VIP para usuario\n"
        "/listusers — Listar usuarios\n"
        "/listvideos — Listar videos\n"
        "/delvideo — Remover video\n"
        "/listpayments — Pagamentos pendentes\n"
        "/broadcast — Enviar mensagem para todos\n"
        "/config — Configuracoes gerais\n"
        "/search_videos — Buscar videos (Pexels)",
        parse_mode=ParseMode.HTML,
    )


async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_admin(update.effective_user.id):
        await update.message.reply_text(
            f"<b>File ID:</b>\n<code>{update.message.video.file_id}</code>\n\n"
            "Use: responda ao video com\n/upload Titulo | Categoria | Preco | sim/nao",
            parse_mode=ParseMode.HTML,
        )


# ─────────────────────────────────────────────
# HEALTH CHECK SERVER (Render/Railway)
# ─────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot VIP - Online!")

    def log_message(self, format, *args):
        pass


def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    logger.info(f"Health check server rodando na porta {port}")
    server.serve_forever()


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
def build_app():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("upload", upload_command))
    app.add_handler(CommandHandler("upload_low", upload_low_command))
    app.add_handler(CommandHandler("add_url", add_url_command))
    app.add_handler(CommandHandler("addvip", addvip_command))
    app.add_handler(CommandHandler("listusers", listusers_command))
    app.add_handler(CommandHandler("listvideos", listvideos_command))
    app.add_handler(CommandHandler("delvideo", delvideo_command))
    app.add_handler(CommandHandler("listpayments", listpayments_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("config", config_command))
    app.add_handler(CommandHandler("search_videos", search_videos_command))

    app.add_handler(CallbackQueryHandler(referral_handler, pattern=r"^referral$"))
    app.add_handler(CallbackQueryHandler(catalog_handler, pattern=r"^menu_cats$"))
    app.add_handler(CallbackQueryHandler(cat_videos_handler, pattern=r"^cat_"))
    app.add_handler(CallbackQueryHandler(play_video_handler, pattern=r"^play_"))
    app.add_handler(CallbackQueryHandler(random_content_handler, pattern=r"^random_content$"))
    app.add_handler(CallbackQueryHandler(vip_handler, pattern=r"^vip$"))
    app.add_handler(CallbackQueryHandler(plan_handler, pattern=r"^plan_"))
    app.add_handler(CallbackQueryHandler(pixmp_handler, pattern=r"^pixmp_"))
    app.add_handler(CallbackQueryHandler(pixmanual_handler, pattern=r"^pixmanual_"))
    app.add_handler(CallbackQueryHandler(tonpay_handler, pattern=r"^tonpay_"))
    app.add_handler(CallbackQueryHandler(status_handler, pattern=r"^status$"))
    app.add_handler(CallbackQueryHandler(start, pattern=r"^home$"))

    app.add_handler(MessageHandler(filters.VIDEO, handle_video))

    return app


async def run_bot():
    app = build_app()
    async with app:
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True, poll_interval=1.0)
        logger.info("Bot Online — PIX + TON automaticos ativos!")
        while True:
            await asyncio.sleep(3600)


def main():
    init_db()

    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()

    while True:
        try:
            asyncio.run(run_bot())
        except (KeyboardInterrupt, SystemExit):
            logger.info("Bot encerrado.")
            break
        except Exception as e:
            logger.error(f"Erro: {e}. Reconectando em 5s...")
            time.sleep(5)


if __name__ == "__main__":
    main()
