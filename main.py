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
        price REAL DEFAULT 0,
        category TEXT,
        is_vip_content BOOLEAN DEFAULT FALSE)''')
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

def get_main_menu_keyboard(user_id):
    user = db_query('SELECT test_used FROM users WHERE user_id = ?', (user_id,), fetchone=True)
    test_used = user[0] if user else False
    kb = [[InlineKeyboardButton("🔞 VER CONTEÚDOS EXCLUSIVOS", callback_data='menu_cats')]]
    if not test_used:
        kb.append([InlineKeyboardButton("🎁 TESTE VIP GRÁTIS (3 DIAS)", callback_data='vip_test')])
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

    txt = (
        f"🔥 Olá, {user.full_name}! Seja muito bem-vindo(a)! 🔥\n\n"
        f"Aqui você encontra os melhores conteúdos exclusivos. 😈\n\n"
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
        await query.edit_message_caption("🔥 *MENU PRINCIPAL*\n\nO que você deseja ver agora?", reply_markup=get_main_menu_keyboard(uid), parse_mode='Markdown')

    elif data == 'vip_test':
        user = db_query('SELECT test_used FROM users WHERE user_id = ?', (uid,), fetchone=True)
        if user and user[0]:
            await query.edit_message_caption("❌ Você já usou o teste grátis!", reply_markup=get_main_menu_keyboard(uid))
        else:
            expires = (datetime.now() + timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S')
            db_query('UPDATE users SET vip_expires = ?, test_used = 1 WHERE user_id = ?', (expires, uid))
            await query.edit_message_caption(f"✅ *VIP ATIVADO!* 💎\n\nVocê ganhou 3 dias de acesso grátis até {expires}!", reply_markup=get_main_menu_keyboard(uid), parse_mode='Markdown')

    elif data == 'menu_cats':
        cats = db_query('SELECT DISTINCT category FROM videos', fetchall=True)
        if not cats:
            await query.edit_message_caption("📂 *CATÁLOGO EM ATUALIZAÇÃO...*", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 VOLTAR", callback_data='menu_main')]]), parse_mode='Markdown')
            return
        kb = [[InlineKeyboardButton(f"📁 {c[0].upper()}", callback_data=f'cat_{c[0]}')] for c in cats]
        kb.append([InlineKeyboardButton("🔙 VOLTAR", callback_data='menu_main')])
        await query.edit_message_caption("🔥 *ESCOLHA UMA CATEGORIA:*", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data.startswith('cat_'):
        cat = data.split('_')[1]
        vids = db_query('SELECT id, title FROM videos WHERE category = ?', (cat,), fetchall=True)
        kb = [[InlineKeyboardButton(f"🎬 {v[1]}", callback_data=f'view_{v[0]}')] for v in vids]
        kb.append([InlineKeyboardButton("🔙 VOLTAR", callback_data='menu_cats')])
        await query.edit_message_caption(f"📂 *CATEGORIA: {cat.upper()}*", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data.startswith('view_'):
        vid_id = data.split('_')[1]
        v = db_query('SELECT title, description, file_id, is_vip_content FROM videos WHERE id = ?', (vid_id,), fetchone=True)
        if is_user_vip(uid) or not v[3]:
            try:
                await context.bot.send_video(chat_id=uid, video=v[2], caption=f"🔥 *{v[0]}*\n\n{v[1]}", parse_mode='Markdown')
            except:
                await context.bot.send_message(chat_id=uid, text="❌ Erro ao enviar vídeo.")
        else:
            await query.edit_message_caption("❌ *CONTEÚDO BLOQUEADO*\n\nExclusivo para membros VIP. 💎", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💎 VIRAR VIP AGORA", callback_data='menu_vip')], [InlineKeyboardButton("🔙 VOLTAR", callback_data='menu_cats')]]), parse_mode='Markdown')

    elif data == 'menu_vip':
        txt = "💎 *ACESSO VIP EXCLUSIVO* 💎\n\n💰 *PLANOS:*\n• Mensal: *R$ 50,00*\n• Anual: *R$ 100,00*\n\nEscolha o pagamento:"
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

SEXUAL_CONTENT = [
    "Conteúdo 1",
    "Conteúdo 2",
    "Conteúdo 3"
]

async def send_random_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_user_vip(uid):
        await update.message.reply_text("❌ Você precisa ser VIP para usar este comando.\nUse /start para ver os planos.")
        return
    content = random.choice(SEXUAL_CONTENT)
    await update.message.reply_text(content)

# ==========================================
# 🔍 BUSCA DE VÍDEOS
# ==========================================

SEARCH_URL = "https://exemplo.com/vazados"

async def search_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_user_vip(uid):
        await update.message.reply_text("❌ Você precisa ser VIP para usar este comando.\nUse /start para ver os planos.")
        return
    try:
        response = requests.get(SEARCH_URL, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        videos = soup.find_all('div', class_='video-item')
        if not videos:
            await update.message.reply_text("📂 Nenhum vídeo encontrado no momento.")
            return
        for video in videos:
            video_url = video.find('a')['href']
            video_title = video.find('h3').text
            await update.message.reply_text(f"🎬 Novo vídeo: {video_title}\n{video_url}")
    except Exception as e:
        logger.error(f"Erro ao buscar vídeos: {e}")
        await update.message.reply_text("❌ Erro ao buscar vídeos. Tente novamente mais tarde.")

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
        await update.message.reply_text("Formato: /upload Titulo | Categoria | Preco | sim/nao")
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
    vip_label = "SIM" if is_vip else "NAO"
    await update.message.reply_text(
        f"✅ Vídeo salvo!\n\n"
        f"📌 Título: {title}\n"
        f"📁 Categoria: {category}\n"
        f"💰 Preço: R$ {price:.2f}\n"
        f"💎 VIP: {vip_label}\n"
        f"🆔 File ID: {file_id}"
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
            "  /config broadcast <mensagem>",
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
    app.add_handler(CommandHandler("upload", upload_command))
    app.add_handler(CommandHandler("config", config_command))
    app.add_handler(CommandHandler("listusers", listusers_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    logger.info("🚀 Bot iniciado com todas as melhorias!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
