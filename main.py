import logging
import sqlite3
import os
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

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

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    logger.info("🚀 Bot com vídeo restaurado iniciado!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
