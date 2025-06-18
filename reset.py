import logging
import re
import requests
import asyncio
import random
from time import time
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from telegram.constants import ParseMode

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

BOT_TOKEN = '7922978245:AAF35htgae7l3p6Q4Ha3uin8D2irsI-2SXY'
ADMIN_CHAT_ID = 7820943202

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15',
    'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:112.0) Gecko/20100101 Firefox/112.0',
]

user_cooldowns = {}
COOLDOWN_SECONDS = 300
USE_TOR = True

def escape(text: str) -> str:
    return re.sub(r'([_*[]()~`>#+\-=|{}.!])', r'\\', text)

def extract_email(text: str) -> str:
    m = re.search('<b>(.*?)</b>', text)
    return m.group(1) if m else "Unknown"

def send_reset_request(username: str, use_tor=False):
    try:
        user_agent = random.choice(USER_AGENTS)
        session = requests.Session()

        if use_tor:
            session.proxies = {
                'http': 'socks5h://127.0.0.1:9050',
                'https': 'socks5h://127.0.0.1:9050',
            }

        response = session.post(
            'https://www.instagram.com/accounts/account_recovery_send_ajax/',
            headers={
                'User-Agent': user_agent,
                'Referer': 'https://www.instagram.com/accounts/password/reset/',
                'X-CSRFToken': 'csrftoken'
            },
            data={'email_or_username': username},
            timeout=15
        )

        if response.status_code == 429:
            return False, "Too many requests — please wait and try again later."
        elif response.status_code == 403:
            return False, "Access forbidden — your IP might be blocked."
        elif response.status_code == 200:
            masked = extract_email(response.text)
            return True, masked
        else:
            return False, f"Reset failed or username not found (status {response.status_code})."

    except requests.exceptions.RequestException as e:
        return False, f"Request failed: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome! Use /reset or /mass to begin.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_username"] = True
    await update.message.reply_text("⏳ Please send the Instagram username or email:")

async def mass_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📋 *Mass Reset Mode Enabled!*\nSend usernames separated by space, comma or newline:",
        parse_mode=ParseMode.MARKDOWN
    )
    context.user_data["awaiting_mass_reset"] = True

async def send_cooldown_progress(update: Update, context: ContextTypes.DEFAULT_TYPE, seconds_left: int):
    chat_id = update.effective_chat.id
    message = await update.message.reply_text("⏳ Cooldown active, please wait...", parse_mode=ParseMode.MARKDOWN)
    bar_length = 20
    for remaining in range(seconds_left, -1, -1):
        filled_length = int((bar_length * (seconds_left - remaining)) / seconds_left)
        bar = '▓' * filled_length + '░' * (bar_length - filled_length)
        text = f"⏳ Cooldown in progress:\n`[{bar}] {remaining}s remaining`"
        try:
            await context.bot.edit_message_text(chat_id=chat_id, message_id=message.message_id, text=text, parse_mode=ParseMode.MARKDOWN)
        except Exception:
            pass
        if remaining > 0:
            await asyncio.sleep(1)

    await context.bot.edit_message_text(chat_id=chat_id, message_id=message.message_id, text="✅ Cooldown finished! You can send your reset request now.", parse_mode=ParseMode.MARKDOWN)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    now = time()
    last_request = user_cooldowns.get(user_id, 0)
    elapsed = now - last_request
    if elapsed < COOLDOWN_SECONDS:
        seconds_left = int(COOLDOWN_SECONDS - elapsed)
        await send_cooldown_progress(update, context, seconds_left)
        return
    user_cooldowns[user_id] = now

    chat_id = update.effective_chat.id
    username_input = update.message.text.strip()
    telegram_username = update.effective_user.username or "Unknown"
    time_now = datetime.now().strftime("%d-%b-%Y %I:%M %p")

    if context.user_data.get("awaiting_mass_reset"):
        context.user_data["awaiting_mass_reset"] = False
        usernames = re.split(r'[\s,]+', username_input)
        await update.message.reply_text(f"📦 Processing {len(usernames)} usernames...")

        for idx, username in enumerate(usernames, 1):
            if not username:
                continue
            await update.message.reply_text(f"🔄 [{idx}/{len(usernames)}] Processing `{username}`...", parse_mode=ParseMode.MARKDOWN)
            await asyncio.sleep(random.uniform(2, 5))
            success, result = send_reset_request(username, use_tor=USE_TOR)
            status_text = (
                f"✅ Sent to `{username}` — Masked: `{result}`"
                if success else
                f"❌ Failed for `{username}` — {result}"
            )
            await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN)
        return

    if not context.user_data.get("awaiting_username"):
        await update.message.reply_text("ℹ️ Please use /reset or /mass before sending usernames.")
        return

    context.user_data["awaiting_username"] = False
    await asyncio.sleep(random.uniform(2, 5))
    success, result = send_reset_request(username_input, use_tor=USE_TOR)

    if success:
        await update.message.reply_text(f"✅ Sent to `{username_input}` — Masked: `{result}`", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"❌ Failed: {result}")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(CommandHandler("mass", mass_reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logging.info("🤖 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()