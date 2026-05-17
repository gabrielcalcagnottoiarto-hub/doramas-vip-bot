import logging
import sqlite3
import os
import asyncio
import random
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# ==========================================
# ⚙️ CONFIGURAÇÕES REAIS DO USUÁRIO
# ==========================================
TOKEN = "8807988771:AAFOhkmeaegPyncueb7rNKUceC9sAtJQMR8"
ADMIN_ID = 1845718197
DB_NAME = "users.db"
PIX_KEY = "00906203058"
TON_WALLET = "UQDn8qu6wduopti68NN9aFjJ0ORN8diPtuUMuR8_7tQG7lai"

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==========================================
# 🗄️ BANCO DE DADOS
# ==========================================
def db_query(query, params=(), fetchone=False, fetchall=False):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(query, params)
        res = cursor.fetchone() if fetchone else (cursor.fetchall() if fetchall else None)
        conn.commit()
        conn.close()
        return res
    except Exception as e:
        logger.error(f"Erro no banco de dados: {e}")
        return None

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        is_vip BOOLEAN DEFAULT FALSE,
        vip_expires DATETIME,
        test_used BOOLEAN DEFAULT FALSE,
        joined_at DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        file_id TEXT,
        file_id_low TEXT,
        price REAL DEFAULT 0,
        category TEXT,
        is_vip_content BOOLEAN DEFAULT FALSE)''')
    # Adicionar coluna file_id_low se nao existir (migracao)
    try:
        cursor.execute('ALTER TABLE videos ADD COLUMN file_id_low TEXT')
    except Exception:
        pass
    conn.commit()
    conn.close()

def is_user_vip(user_id):
    user = db_query('SELECT is_vip, vip_expires FROM users WHERE user_id = ?', (user_id,), fetchone=True)
    if not user: return False
    is_vip, expires = user
    if is_vip: return True
    if expires:
        try:
            expire_date = datetime.strptime(expires, '%Y-%m-%d %H:%M:%S')
            if expire_date > datetime.now(): return True
        except: pass
    return False

def get_ad_text():
    """Retorna o texto de propaganda configurado pelo admin."""
    ad = db_query('SELECT value FROM config WHERE key = ?', ('ad_text',), fetchone=True)
    return ad[0] if ad else "📢 Quer conteúdo em HD sem propagandas? Assine VIP! Use /start"

def get_main_menu_keyboard(user_id):
    user = db_query('SELECT test_used FROM users WHERE user_id = ?', (user_id,), fetchone=True)
    test_used = user[0] if user else False
    vip = is_user_vip(user_id)
    kb = []
    if vip:
        kb.append([InlineKeyboardButton("🔞 VER CONTEÚDOS VIP (HD)", callback_data='menu_cats_vip')])
    kb.append([InlineKeyboardButton("🆓 VER CONTEÚDOS GRÁTIS", callback_data='menu_cats_free')])
    if not test_used:
        kb.append([InlineKeyboardButton("🎁 TESTE VIP GRÁTIS (3 DIAS)", callback_data='vip_test')])
    if not vip:
        kb.append([InlineKeyboardButton("💎 ACESSO VIP (LIBERA TUDO)", callback_data='menu_vip')])
    kb.append([InlineKeyboardButton("💳 COMO PAGAR AGORA", callback_data='menu_pay')])
    return InlineKeyboardMarkup(kb)

# ==========================================
# 👤 INTERFACE DO USUÁRIO
# ==========================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    user = update.effective_user
    db_query('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (user.id, user.username))

    vip = is_user_vip(user.id)
    if vip:
        txt = (
            f"🔥 Olá, {user.full_name}! Seja muito bem-vindo(a)! 🔥\n\n"
            f"Você é VIP! 💎 Acesso total em HD sem propagandas. 😈\n\n"
            f"Escolha uma das opções abaixo e aproveite!"
        )
    else:
        txt = (
            f"🔥 Olá, {user.full_name}! Seja muito bem-vindo(a)! 🔥\n\n"
            f"Aqui você encontra os melhores conteúdos exclusivos. 😈\n"
            f"🆓 Conteúdo grátis disponível (resolução baixa + propagandas)\n"
            f"💎 Assine VIP para HD + mais conteúdo + sem propagandas!\n\n"
            f"Escolha uma das opções abaixo e aproveite!"
        )

    kb = get_main_menu_keyboard(user.id)
    video_path = 'welcome_video.mp4'

    # Tentar enviar o vídeo em cache primeiro para ser rápido
    cached_video = db_query('SELECT value FROM config WHERE key = ?', ('welcome_video_id',), fetchone=True)
    if cached_video:
        try:
            await update.message.reply_video(video=cached_video[0], caption=txt, reply_markup=kb)
            return
        except:
            logger.info("Cache de vídeo falhou, enviando arquivo físico...")

    # Se falhar o cache, envia o arquivo físico e atualiza o ID
    if os.path.exists(video_path):
        try:
            with open(video_path, 'rb') as v:
                sent_msg = await update.message.reply_video(video=v, caption=txt, reply_markup=kb)
                db_query('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', ('welcome_video_id', sent_msg.video.file_id))
        except Exception as e:
            logger.error(f"Erro ao enviar vídeo físico: {e}")
            await update.message.reply_text(txt, reply_markup=kb)
    else:
        await update.message.reply_text(txt, reply_markup=kb)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query: return
    await query.answer()
    uid = query.from_user.id
    data = query.data

    if data == 'menu_main':
        vip = is_user_vip(uid)
        if vip:
            await query.edit_message_caption("🔥 *MENU PRINCIPAL* 💎\n\nVocê é VIP! Acesso total em HD.", reply_markup=get_main_menu_keyboard(uid), parse_mode='Markdown')
        else:
            await query.edit_message_caption("🔥 *MENU PRINCIPAL*\n\nConteúdo grátis (baixa resolução) ou assine VIP!", reply_markup=get_main_menu_keyboard(uid), parse_mode='Markdown')

    elif data == 'vip_test':
        user = db_query('SELECT test_used FROM users WHERE user_id = ?', (uid,), fetchone=True)
        if user and user[0]:
            await query.edit_message_caption("❌ Você já usou o teste grátis!", reply_markup=get_main_menu_keyboard(uid))
        else:
            expires = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
            db_query('UPDATE users SET vip_expires = ?, test_used = 1 WHERE user_id = ?', (expires, uid))
            await query.edit_message_caption(f"✅ *VIP ATIVADO!* 💎\n\nVocê ganhou 3 dias de acesso grátis até {expires}!", reply_markup=get_main_menu_keyboard(uid), parse_mode='Markdown')

    elif data == 'menu_cats_vip':
        if not is_user_vip(uid):
            await query.edit_message_caption("❌ *ACESSO VIP NECESSÁRIO*\n\nAssine VIP para ver conteúdo em HD!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 VIRAR VIP AGORA", callback_data='menu_vip')], [InlineKeyboardButton("🔙 VOLTAR", callback_data='menu_main')]]), parse_mode='Markdown')
            return
        cats = db_query('SELECT DISTINCT category FROM videos', fetchall=True)
        if not cats:
            await query.edit_message_caption("📂 *CATÁLOGO VIP EM ATUALIZAÇÃO...*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 VOLTAR", callback_data='menu_main')]]), parse_mode='Markdown')
            return
        kb = [[InlineKeyboardButton(f"📁 {c[0].upper()} (HD)", callback_data=f'catvip_{c[0]}')] for c in cats]
        kb.append([InlineKeyboardButton("🔙 VOLTAR", callback_data='menu_main')])
        await query.edit_message_caption("💎 *CATÁLOGO VIP — RESOLUÇÃO HD:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data == 'menu_cats_free':
        cats = db_query('SELECT DISTINCT category FROM videos', fetchall=True)
        if not cats:
            await query.edit_message_caption("📂 *CATÁLOGO EM ATUALIZAÇÃO...*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 VOLTAR", callback_data='menu_main')]]), parse_mode='Markdown')
            return
        kb = [[InlineKeyboardButton(f"📁 {c[0].upper()}", callback_data=f'catfree_{c[0]}')] for c in cats]
        kb.append([InlineKeyboardButton("🔙 VOLTAR", callback_data='menu_main')])
        await query.edit_message_caption("🆓 *CATÁLOGO GRÁTIS — RESOLUÇÃO BAIXA:*\n\n⚠️ Contém propagandas. Assine VIP para HD!", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data.startswith('catvip_'):
        cat = data[7:]
        vids = db_query('SELECT id, title FROM videos WHERE category = ?', (cat,), fetchall=True)
        kb = [[InlineKeyboardButton(f"🎬 {v[1]} (HD)", callback_data=f'viewvip_{v[0]}')] for v in vids]
        kb.append([InlineKeyboardButton("🔙 VOLTAR", callback_data='menu_cats_vip')])
        await query.edit_message_caption(f"💎 *{cat.upper()} — HD:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data.startswith('catfree_'):
        cat = data[8:]
        vids = db_query('SELECT id, title FROM videos WHERE category = ?', (cat,), fetchall=True)
        kb = [[InlineKeyboardButton(f"🎬 {v[1]}", callback_data=f'viewfree_{v[0]}')] for v in vids]
        kb.append([InlineKeyboardButton("🔙 VOLTAR", callback_data='menu_cats_free')])
        await query.edit_message_caption(f"🆓 *{cat.upper()} — GRÁTIS:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data.startswith('viewvip_'):
        vid_id = data[8:]
        v = db_query('SELECT title, description, file_id FROM videos WHERE id = ?', (vid_id,), fetchone=True)
        if not is_user_vip(uid):
            await query.edit_message_caption("❌ *CONTEÚDO VIP BLOQUEADO*\n\nAssine VIP para HD sem propagandas! 💎", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 VIRAR VIP AGORA", callback_data='menu_vip')], [InlineKeyboardButton("🔙 VOLTAR", callback_data='menu_cats_vip')]]), parse_mode='Markdown')
            return
        try:
            await context.bot.send_video(chat_id=uid, video=v[2], caption=f"💎 *{v[0]}* (HD)\n\n{v[1]}", parse_mode='Markdown')
        except Exception:
            await context.bot.send_message(chat_id=uid, text="❌ Erro ao enviar vídeo.")

    elif data.startswith('viewfree_'):
        vid_id = data[9:]
        v = db_query('SELECT title, description, file_id, file_id_low FROM videos WHERE id = ?', (vid_id,), fetchone=True)
        ad = get_ad_text()
        # Enviar propaganda antes do conteudo
        await context.bot.send_message(chat_id=uid, text=f"📢 *PROPAGANDA:*\n\n{ad}\n\n💎 Assine VIP para remover propagandas!", parse_mode='Markdown')
        video_to_send = v[3] if v[3] else v[2]  # Usar versao baixa se disponivel
        try:
            caption = f"🆓 *{v[0]}* (Resolução Baixa)\n\n{v[1]}\n\n📢 {ad}"
            await context.bot.send_video(chat_id=uid, video=video_to_send, caption=caption, parse_mode='Markdown')
        except Exception:
            await context.bot.send_message(chat_id=uid, text="❌ Erro ao enviar vídeo.")

    elif data == 'menu_vip':
        txt = (
            "💎 *ACESSO VIP EXCLUSIVO* 💎\n\n"
            "✅ Vídeos em *ALTA RESOLUÇÃO (HD)*\n"
            "✅ *Muito mais conteúdo* exclusivo\n"
            "✅ *Sem propagandas*\n"
            "✅ Acesso a *todos os comandos* premium\n\n"
            "💰 *PLANOS:*\n"
            "• Mensal: *R$ 50,00*\n"
            "• Anual: *R$ 100,00*\n\n"
            "Escolha o pagamento:"
        )
        kb = [[InlineKeyboardButton("💳 Pagar com PIX", callback_data='pay_pix')], [InlineKeyboardButton("🪙 Pagar com Toncoin (Tonkeeper)", callback_data='pay_ton')], [InlineKeyboardButton("🔙 VOLTAR", callback_data='menu_main')]]
        await query.edit_message_caption(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data == 'pay_pix':
        txt = f"💳 *PAGAMENTO VIA PIX*\n\n📍 Chave PIX: `{PIX_KEY}`\n\n⚠️ Envie o comprovante para o suporte!"
        await query.edit_message_caption(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 VOLTAR", callback_data='menu_vip')]]), parse_mode='Markdown')

    elif data == 'pay_ton':
        link_mensal = f"ton://transfer/{TON_WALLET}?amount=5000000000"
        link_anual = f"ton://transfer/{TON_WALLET}?amount=10000000000"
        web_mensal = f"https://tonkeeper.com/transfer/{TON_WALLET}?amount=5000000000"
        web_anual = f"https://tonkeeper.com/transfer/{TON_WALLET}?amount=10000000000"
        txt = "🪙 *PAGAMENTO VIA TONCOIN*\n\nClique para pagar com Tonkeeper:"
        kb = [
            [InlineKeyboardButton("💎 MENSAL DIRETO", url=link_mensal), InlineKeyboardButton("🌐 WEB", url=web_mensal)],
            [InlineKeyboardButton("🔥 ANUAL DIRETO", url=link_anual), InlineKeyboardButton("🌐 WEB", url=web_anual)],
            [InlineKeyboardButton("🔙 VOLTAR", callback_data='menu_vip')]
        ]
        await query.edit_message_caption(txt, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data == 'menu_pay':
        await query.edit_message_caption("💳 *PAGAMENTO*\n\nAceitamos PIX e Toncoin.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 VOLTAR", callback_data='menu_main')]]), parse_mode='Markdown')

# ==========================================
# 🎲 CONTEÚDO ALEATÓRIO (VIP)
# ==========================================

SEXUAL_CONTENT_FREE = [
    "🆓 Prévia 1 — Conteúdo de amostra (resolução baixa)",
    "🆓 Prévia 2 — Conteúdo de amostra (resolução baixa)",
    "🆓 Prévia 3 — Conteúdo de amostra (resolução baixa)"
]

SEXUAL_CONTENT_VIP = [
    "💎 Conteúdo VIP 1 — Exclusivo HD",
    "💎 Conteúdo VIP 2 — Exclusivo HD",
    "💎 Conteúdo VIP 3 — Exclusivo HD",
    "💎 Conteúdo VIP 4 — Exclusivo HD",
    "💎 Conteúdo VIP 5 — Exclusivo HD",
    "💎 Conteúdo VIP 6 — Exclusivo HD",
    "💎 Conteúdo VIP 7 — Exclusivo HD",
    "💎 Conteúdo VIP 8 — Exclusivo HD",
    "💎 Conteúdo VIP 9 — Exclusivo HD",
    "💎 Conteúdo VIP 10 — Exclusivo HD"
]

async def send_random_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if is_user_vip(uid):
        content = random.choice(SEXUAL_CONTENT_VIP)
        await update.message.reply_text(f"{content}\n\n💎 Conteúdo exclusivo VIP em alta resolução!")
    else:
        content = random.choice(SEXUAL_CONTENT_FREE)
        ad = get_ad_text()
        await update.message.reply_text(
            f"{content}\n\n"
            f"📢 *PROPAGANDA:* {ad}\n\n"
            f"💎 Assine VIP para mais conteúdo em HD sem propagandas!\n"
            f"Use /start para ver os planos.",
            parse_mode='Markdown'
        )

# ==========================================
# 🔍 BUSCA DE VÍDEOS — PEXELS API (Gratuita)
# ==========================================

PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "")

async def search_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    vip = is_user_vip(uid)

    api_key = db_query('SELECT value FROM config WHERE key = ?', ('pexels_api_key',), fetchone=True)
    key = api_key[0] if api_key else PEXELS_API_KEY
    if not key:
        await update.message.reply_text("⚠️ API Pexels não configurada.\nAdmin: /config pexels <sua_api_key>\nObtenha grátis em: https://www.pexels.com/api/")
        return

    query = " ".join(context.args) if context.args else "sexy"
    per_page = 5 if vip else 2  # VIP recebe mais resultados
    try:
        headers = {"Authorization": key}
        response = requests.get(
            f"https://api.pexels.com/v1/videos/search?query={query}&per_page={per_page}&locale=pt-BR",
            headers=headers, timeout=10
        )
        data = response.json()
        videos = data.get('videos', [])
        if not videos:
            await update.message.reply_text(f"📂 Nenhum vídeo encontrado para: {query}")
            return

        if not vip:
            ad = get_ad_text()
            await update.message.reply_text(f"📢 *PROPAGANDA:* {ad}\n\n💎 Assine VIP para resultados em HD sem propagandas!", parse_mode='Markdown')

        for v in videos:
            video_url = v.get('url', '')
            user_name = v.get('user', {}).get('name', 'Desconhecido')
            duration = v.get('duration', 0)

            if vip:
                # VIP: resolucao HD
                hd_link = ''
                for vf in v.get('video_files', []):
                    if vf.get('quality') == 'hd':
                        hd_link = vf.get('link', '')
                        break
                if not hd_link and v.get('video_files'):
                    hd_link = v['video_files'][0].get('link', '')
                await update.message.reply_text(
                    f"💎 *{user_name}* ({duration}s) — HD\n"
                    f"🔗 Pexels: {video_url}\n"
                    f"📥 Download HD: {hd_link}",
                    parse_mode='Markdown'
                )
            else:
                # GRATIS: resolucao SD (mais baixa)
                sd_link = ''
                for vf in v.get('video_files', []):
                    if vf.get('quality') == 'sd':
                        sd_link = vf.get('link', '')
                        break
                if not sd_link and v.get('video_files'):
                    sd_link = v['video_files'][0].get('link', '')
                await update.message.reply_text(
                    f"🆓 *{user_name}* ({duration}s) — Baixa Resolução\n"
                    f"🔗 Pexels: {video_url}\n"
                    f"📥 Download SD: {sd_link}\n\n"
                    f"💎 _Assine VIP para download em HD!_",
                    parse_mode='Markdown'
                )

        if not vip:
            ad = get_ad_text()
            await update.message.reply_text(f"📢 {ad}\n\n💎 Assine VIP: mais resultados + HD + sem propagandas!\nUse /start para ver planos.")

    except Exception as e:
        logger.error(f"Erro ao buscar vídeos Pexels: {e}")
        await update.message.reply_text("❌ Erro ao buscar vídeos. Tente novamente mais tarde.")

# ==========================================
# 🌐 BUSCA DE FILMES/SÉRIES — TMDB API (Gratuita)
# ==========================================

TMDB_API_KEY = os.environ.get("TMDB_API_KEY", "")

async def search_api(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    vip = is_user_vip(uid)

    api_key = db_query('SELECT value FROM config WHERE key = ?', ('tmdb_api_key',), fetchone=True)
    key = api_key[0] if api_key else TMDB_API_KEY
    if not key:
        await update.message.reply_text("⚠️ API TMDB não configurada.\nAdmin: /config tmdb <sua_api_key>\nObtenha grátis em: https://www.themoviedb.org/settings/api")
        return

    query = " ".join(context.args) if context.args else ""
    if not query:
        await update.message.reply_text("Uso: /search_api <nome do filme ou série>\nExemplo: /search_api filme")
        return

    max_results = 5 if vip else 2  # VIP recebe mais resultados
    try:
        response = requests.get(
            f"https://api.themoviedb.org/3/search/multi?api_key={key}&query={query}&language=pt-BR&page=1",
            timeout=10
        )
        data = response.json()
        results = data.get('results', [])[:max_results]
        if not results:
            await update.message.reply_text(f"📂 Nenhum resultado para: {query}")
            return

        if not vip:
            ad = get_ad_text()
            await update.message.reply_text(f"📢 *PROPAGANDA:* {ad}", parse_mode='Markdown')

        for item in results:
            media_type = item.get('media_type', 'movie')
            title = item.get('title') or item.get('name', 'Sem título')
            overview = item.get('overview', 'Sem descrição')[:200]
            rating = item.get('vote_average', 0)
            year = (item.get('release_date') or item.get('first_air_date') or '')[:4]
            poster = item.get('poster_path', '')
            tipo = "🎬 Filme" if media_type == 'movie' else "📺 Série"
            tmdb_url = f"https://www.themoviedb.org/{media_type}/{item.get('id')}"

            if vip:
                poster_url = f"https://image.tmdb.org/t/p/w500{poster}" if poster else ''
                msg = f"💎 {tipo}: *{title}*"
                if year:
                    msg += f" ({year})"
                msg += f"\n⭐ {rating}/10\n\n{overview}\n\n🔗 {tmdb_url}"
                if poster_url:
                    msg += f"\n🖼 {poster_url}"
            else:
                poster_url = f"https://image.tmdb.org/t/p/w92{poster}" if poster else ''
                msg = f"🆓 {tipo}: *{title}*"
                if year:
                    msg += f" ({year})"
                msg += f"\n⭐ {rating}/10\n\n{overview[:100]}..."
                msg += f"\n\n💎 _Assine VIP para ver descrição completa e poster HD!_"

            await update.message.reply_text(msg, parse_mode='Markdown')

        if not vip:
            ad = get_ad_text()
            await update.message.reply_text(f"📢 {ad}\n\n💎 Assine VIP: mais resultados + detalhes completos!\nUse /start para ver planos.")

    except Exception as e:
        logger.error(f"Erro ao buscar na TMDB: {e}")
        await update.message.reply_text("❌ Erro ao buscar filmes. Tente novamente mais tarde.")

# ==========================================
# 🛠️ COMANDOS ADMIN
# ==========================================

async def upload_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /upload Titulo | Categoria | Preco | sim/nao (VIP)
    Envie como resposta a um vídeo."""
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text(
            "Uso: /upload Titulo | Categoria | Preco | sim/nao\n"
            "Envie como resposta a um vídeo.\n\n"
            "Exemplo: /upload Filme Top | acao | 0 | sim"
        )
        return
    if not update.message.reply_to_message or not update.message.reply_to_message.video:
        await update.message.reply_text("⚠️ Responda a um vídeo com o comando /upload.")
        return

    text = " ".join(context.args)
    parts = [p.strip() for p in text.split("|")]
    if len(parts) < 4:
        await update.message.reply_text(
            "Formato: /upload Titulo | Categoria | Preco | sim/nao\n\n"
            "Envie como resposta a um vídeo.\n\n"
            "Exemplo: /upload Filme Top | acao | 0 | sim\n\n"
            "💡 Para adicionar versão baixa resolução:\n"
            "/upload_low <id_do_video>\n"
            "(responda a um vídeo em baixa resolução)"
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
        'INSERT INTO videos (title, description, file_id, price, category, is_vip_content) VALUES (?, ?, ?, ?, ?, ?)',
        (title, "", file_id, price, category, is_vip)
    )
    vid = db_query('SELECT last_insert_rowid()', fetchone=True)
    vid_id = vid[0] if vid else '?'
    vip_label = "SIM" if is_vip else "NAO"
    await update.message.reply_text(
        f"✅ Vídeo salvo (HD)!\n\n"
        f"🆔 ID: {vid_id}\n"
        f"📌 Título: {title}\n"
        f"📁 Categoria: {category}\n"
        f"💰 Preço: R$ {price:.2f}\n"
        f"💎 VIP: {vip_label}\n"
        f"🆔 File ID: {file_id}\n\n"
        f"💡 Para adicionar versão baixa resolução:\n"
        f"Responda a um vídeo SD com: /upload_low {vid_id}"
    )

async def upload_low_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /upload_low <video_id> — responda a um video em baixa resolucao."""
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text("Uso: /upload_low <id_do_video>\nResponda a um vídeo em baixa resolução.")
        return
    if not update.message.reply_to_message or not update.message.reply_to_message.video:
        await update.message.reply_text("⚠️ Responda a um vídeo em baixa resolução com o comando /upload_low.")
        return
    try:
        vid_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID do vídeo inválido.")
        return
    v = db_query('SELECT title FROM videos WHERE id = ?', (vid_id,), fetchone=True)
    if not v:
        await update.message.reply_text(f"❌ Vídeo #{vid_id} não encontrado.")
        return
    file_id_low = update.message.reply_to_message.video.file_id
    db_query('UPDATE videos SET file_id_low = ? WHERE id = ?', (file_id_low, vid_id))
    await update.message.reply_text(
        f"✅ Versão baixa resolução salva para: {v[0]} (#{vid_id})\n"
        f"🆔 File ID (SD): {file_id_low}\n\n"
        f"Usuários grátis verão esta versão + propaganda.\n"
        f"VIP verão a versão HD original."
    )

async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /config <sub> <valor>"""
    if update.effective_user.id != ADMIN_ID: return
    if not context.args:
        await update.message.reply_text(
            "⚙️ *Comandos de Configuração:*\n\n"
            "  /config pix <chave_pix>\n"
            "  /config vip <user_id> [dias]\n"
            "  /config ad <texto_do_anuncio>\n"
            "  /config broadcast <mensagem>\n"
            "  /config pexels <api_key>\n"
            "  /config tmdb <api_key>\n\n"
            "📹 *Upload de Vídeos:*\n"
            "  /upload Titulo | Cat | Preco | sim/nao\n"
            "  /upload_low <id_video> (versao SD)",
            parse_mode='Markdown'
        )
        return

    sub = context.args[0].lower()
    rest = context.args[1:]

    if sub == "pix" and rest:
        global PIX_KEY
        PIX_KEY = rest[0]
        db_query('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', ('pix_key', rest[0]))
        await update.message.reply_text(f"✅ Chave PIX atualizada: {rest[0]}")

    elif sub == "vip" and len(rest) >= 1:
        try:
            uid = int(rest[0])
        except ValueError:
            await update.message.reply_text("❌ ID do usuário inválido.")
            return
        dias = int(rest[1]) if len(rest) > 1 and rest[1].isdigit() else 30
        expires = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d %H:%M:%S')
        db_query('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', (uid, ''))
        db_query('UPDATE users SET is_vip = 1, vip_expires = ? WHERE user_id = ?', (expires, uid))
        await update.message.reply_text(f"✅ VIP ativado por {dias} dias para {uid}!")
        try:
            await context.bot.send_message(chat_id=uid, text=f"🎉 Parabéns! Você recebeu {dias} dias de VIP!")
        except Exception:
            pass

    elif sub == "ad":
        ad_text = " ".join(rest) if rest else ""
        if ad_text:
            db_query('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', ('ad_text', ad_text))
            await update.message.reply_text(f"✅ Anúncio configurado: {ad_text}")
        else:
            db_query('DELETE FROM config WHERE key = ?', ('ad_text',))
            await update.message.reply_text("✅ Anúncio removido.")

    elif sub == "pexels" and rest:
        db_query('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', ('pexels_api_key', rest[0]))
        await update.message.reply_text(f"✅ Pexels API Key configurada!")

    elif sub == "tmdb" and rest:
        db_query('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', ('tmdb_api_key', rest[0]))
        await update.message.reply_text(f"✅ TMDB API Key configurada!")

    elif sub == "broadcast" and rest:
        msg_text = " ".join(rest)
        users = db_query('SELECT user_id FROM users', fetchall=True)
        sent = failed = 0
        if users:
            for row in users:
                try:
                    await context.bot.send_message(chat_id=row[0], text=f"📢 Mensagem da equipe:\n\n{msg_text}")
                    sent += 1
                    await asyncio.sleep(0.05)
                except Exception:
                    failed += 1
        await update.message.reply_text(f"📢 Broadcast!\nEnviado: {sent} | Falhou: {failed}")

    else:
        await update.message.reply_text("❌ Parâmetros inválidos. Use /config sem argumentos para ver o uso.")

async def listusers_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: /listusers"""
    if update.effective_user.id != ADMIN_ID: return
    users = db_query('SELECT user_id, username, is_vip, vip_expires FROM users', fetchall=True)
    if not users:
        await update.message.reply_text("Nenhum usuário cadastrado.")
        return
    lines = [f"👥 Usuários ({len(users)})\n"]
    for u in users[:50]:
        status = "💎 VIP" if u[2] else "FREE"
        name = u[1] or str(u[0])
        lines.append(f"- {u[0]} ({name}) [{status}]")
    if len(users) > 50:
        lines.append(f"\n... e mais {len(users) - 50} usuários.")
    await update.message.reply_text("\n".join(lines))

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Quando o admin envia um vídeo, mostra o file_id."""
    if update.effective_user.id == ADMIN_ID:
        file_id = update.message.video.file_id
        await update.message.reply_text(
            f"🆔 File ID do vídeo:\n{file_id}\n\n"
            f"Use: responda ao vídeo com\n/upload Titulo | Categoria | Preco | sim/nao"
        )

def main():
    init_db()

    saved_pix = db_query('SELECT value FROM config WHERE key = ?', ('pix_key',), fetchone=True)
    if saved_pix:
        global PIX_KEY
        PIX_KEY = saved_pix[0]

    app = Application.builder().token(TOKEN).connect_timeout(60).read_timeout(60).write_timeout(60).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("send_content", send_random_content))
    app.add_handler(CommandHandler("search_videos", search_videos))
    app.add_handler(CommandHandler("search_api", search_api))
    app.add_handler(CommandHandler("upload", upload_command))
    app.add_handler(CommandHandler("upload_low", upload_low_command))
    app.add_handler(CommandHandler("config", config_command))
    app.add_handler(CommandHandler("listusers", listusers_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    logger.info("🚀 Bot VIP da Pelada iniciado com sistema FREE + VIP!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
