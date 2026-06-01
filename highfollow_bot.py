import os
import asyncio
import uuid
import time
import random
import json
import re
import secrets
import smtplib
import requests
from threading import Thread

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# ===== CONFIG =====
BOT_TOKEN     = os.environ["BOT_TOKEN_2"]
WORKERS       = 15    # parallel scan workers
MIN_FOLLOWERS = 40    # minimum followers to qualify

# ===== GLOBAL STATE =====
user_tasks: dict[int, bool]       = {}
user_hits:  dict[int, list[str]]  = {}
user_stats: dict[int, dict]       = {}

session   = requests.Session()
ig_tokens = {
    "csrf": "bKPOnxXALzrHjjhgVUSXUWvsJSheI52L",
    "lsd":  "9CaKjXH_JGbfD4zZaTfZ8a",
}


# ===== BACKGROUND TOKEN REFRESHER =====
def _refresh_ig():
    while True:
        try:
            r = session.get(
                "https://www.instagram.com/",
                headers={
                    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                    "x-ig-app-id": "936619743392459",
                    "origin": "https://www.instagram.com",
                },
                timeout=20,
            )
            csrf = r.cookies.get("csrftoken", "")
            m = re.search(r'"LSD",\[\],\{"token":"(.*?)"\}', r.text)
            if csrf and m:
                ig_tokens["csrf"] = csrf
                ig_tokens["lsd"]  = m.group(1)
        except Exception:
            pass
        time.sleep(55)


Thread(target=_refresh_ig, daemon=True).start()


# ===== CORE FUNCTIONS =====
_SEARCH_SEEDS = (
    list("abcdefghijklmnopqrstuvwxyz")
    + ["the", "real", "mr", "ms", "its", "im", "my", "official", "hey", "yo"]
)

def fetch_ig_user() -> tuple[str, str, dict] | None:
    """Fetch a random Instagram user with MIN_FOLLOWERS+ followers."""
    try:
        query = random.choice(_SEARCH_SEEDS) + str(random.randint(1, 9999))
        r = session.get(
            "https://www.instagram.com/web/search/topsearch/",
            params={"query": query, "count": 10, "context": "user"},
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "x-ig-app-id": "936619743392459",
                "x-csrftoken": ig_tokens["csrf"],
                "x-requested-with": "XMLHttpRequest",
                "referer": "https://www.instagram.com/",
                "Accept": "application/json",
            },
            timeout=12,
        )
        results = r.json().get("users", [])
        random.shuffle(results)
        for item in results:
            user = item.get("user", {})
            username  = user.get("username", "")
            followers = user.get("follower_count", 0)
            if username and followers and followers > MIN_FOLLOWERS:
                return username, f"{username}@gmail.com", {
                    "username":       username,
                    "full_name":      user.get("full_name", ""),
                    "follower_count": followers,
                    "following_count": user.get("following_count", 0),
                    "media_count":    user.get("media_count", 0) or 0,
                }
    except Exception:
        pass
    return None


def check_gmail(usr: str) -> bool:
    """
    Returns True if usr@gmail.com is AVAILABLE (account does NOT exist).

    Method A — Gmail API profile (401=exists, 404=available)
    Method B — SMTP RCPT via Google MX (550=available, 250=exists)
    """
    email = f"{usr}@gmail.com"

    # Method A: Gmail REST API with invalid bearer token
    try:
        r = requests.get(
            f"https://gmail.googleapis.com/gmail/v1/users/{email}/profile",
            headers={
                "Authorization": "Bearer ya29.invalid_token_for_check",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=8,
        )
        print(f"[GMAIL] {usr}: API status={r.status_code}")
        if r.status_code == 404:
            return True   # Available
        if r.status_code == 401:
            return False  # Exists
    except Exception as e:
        print(f"[GMAIL] {usr}: API error={e}")

    # Method B: SMTP RCPT verification
    try:
        with smtplib.SMTP("aspmx.l.google.com", 25, timeout=12) as s:
            s.ehlo("mail.verify-check.com")
            s.mail("verify@verify-check.com")
            code, _ = s.rcpt(email)
            print(f"[GMAIL] {usr}: SMTP rcpt code={code}")
            return code == 550  # 550 = rejected = address doesn't exist = available
    except Exception as e:
        print(f"[GMAIL] {usr}: SMTP error={e}")

    return False


def get_linked_email(username: str) -> str | None:
    """Try to get the masked email linked to an Instagram account."""

    # Method 1: Instagram mobile API lookup
    for _ in range(3):
        try:
            r = requests.post(
                "https://i.instagram.com/api/v1/users/lookup/",
                data={"q": username, "skip_recovery": "0"},
                headers={
                    "User-Agent": "Instagram 219.0.0.12.117 Android (28/9; 420dpi; 1080x1920; OnePlus; 6T; OnePlus6T; qcom; en_US)",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "X-IG-App-ID": "567067343352427",
                    "X-IG-Device-ID": str(uuid.uuid4()),
                    "X-IG-Android-ID": "android-" + secrets.token_hex(8),
                    "Accept-Language": "en-US",
                },
                timeout=15,
            )
            data = r.json()
            email = data.get("obfuscated_email") or data.get("email")
            if email:
                return email
        except Exception:
            pass
        time.sleep(0.3)

    # Method 2: Password reset AJAX
    try:
        r = requests.post(
            "https://www.instagram.com/accounts/account_recovery_send_ajax/",
            data={"email_or_username": username, "recaptcha_challenge_field": ""},
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "x-csrftoken": ig_tokens["csrf"],
                "x-instagram-ajax": "1",
                "x-requested-with": "XMLHttpRequest",
                "origin": "https://www.instagram.com",
                "referer": "https://www.instagram.com/accounts/password/reset/",
            },
            cookies={"csrftoken": ig_tokens["csrf"]},
            timeout=15,
        )
        email = r.json().get("email")
        if email:
            return email
    except Exception:
        pass

    return None


# ===== HIT CARD FORMATTER =====
def format_card(hit_num: int, username: str, data: dict, linked_email: str | None) -> str:
    name      = data.get("full_name") or "None"
    followers = data.get("follower_count", "?")
    following = data.get("following_count", "?")
    posts     = data.get("media_count", 0) or 0
    meta      = "True" if posts > 2 else "False"
    mail      = linked_email if linked_email else f"{username}@gmail.com"

    return (
        f"ANKUSH HIGH POST TOOLS AND HIGH FOLLOWERS\n"
        f"TOTAL HIT : {hit_num}\n"
        f"META : {meta}\n"
        f"USERNAME : {username}\n"
        f"MAIL: {mail}\n"
        f"RESET  : https://www.instagram.com/accounts/password/reset/\n"
        f"NAME : {name}\n"
        f"FOLLOWERS : {followers}\n"
        f"FOLLOWING: {following}\n"
        f"DATE: [N/A]\n"
        f"POST : {posts}\n"
        f"LINK : https://www.instagram.com/{username}\n"
        f"_______________________________________\n"
        f"BY ~ @z7rnz"
    )


# Semaphore: max 5 workers send to Telegram at once
_tg_sem = asyncio.Semaphore(5)


# ===== PARALLEL WORKER =====
async def _worker(chat_id: int, app, loop):
    stats = user_stats[chat_id]
    while user_tasks.get(chat_id):
        try:
            result = await loop.run_in_executor(None, fetch_ig_user)
            if result is None:
                stats["bad"] += 1
                await asyncio.sleep(0.2)
                continue

            username, email, data = result
            stats["checked"] += 1

            gmail_ok = await loop.run_in_executor(None, check_gmail, username)
            if not gmail_ok:
                stats["bad"] += 1
                continue

            stats["hits"] += 1
            hit_num = stats["hits"]

            linked_email = await loop.run_in_executor(None, get_linked_email, username)
            card = format_card(hit_num, username, data, linked_email)

            user_hits[chat_id].append({"card": card, "username": username})

            kb = [[
                InlineKeyboardButton("🔍 Profile", url=f"https://www.instagram.com/{username}"),
                InlineKeyboardButton("📋 All Hits", callback_data="show_hits"),
            ]]

            for attempt in range(3):
                try:
                    async with _tg_sem:
                        await app.bot.send_message(chat_id, card, reply_markup=InlineKeyboardMarkup(kb))
                    break
                except Exception:
                    if attempt < 2:
                        await asyncio.sleep(2 ** attempt)

        except Exception:
            await asyncio.sleep(1)


# ===== SCANNER =====
async def run_scanner(chat_id: int, app):
    user_tasks[chat_id] = True
    user_hits[chat_id]  = []
    user_stats[chat_id] = {"hits": 0, "checked": 0, "bad": 0}

    await app.bot.send_message(
        chat_id,
        f"🚀 *ANKUSH HIGH FOLLOW TOOLS STARTED!*\n"
        f"Running `{WORKERS}` parallel workers...\n\n"
        f"📌 Commands:\n"
        f"  /stop — stop the scanner\n"
        f"  /hits — show all hits found\n"
        f"  /status — live stats",
        parse_mode="Markdown",
    )

    loop = asyncio.get_event_loop()
    workers = [asyncio.create_task(_worker(chat_id, app, loop)) for _ in range(WORKERS)]
    await asyncio.gather(*workers)

    total = len(user_hits.get(chat_id, []))
    await app.bot.send_message(
        chat_id,
        f"🛑 *Scanner stopped.*\n"
        f"✅ Total hits: `{total}`\n"
        f"Use /hits to review them.",
        parse_mode="Markdown",
    )


# ===== REPLY KEYBOARD =====
MAIN_KB = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🚀 Start Scan"),  KeyboardButton("🛑 Stop Scan")],
        [KeyboardButton("📋 All Hits"),    KeyboardButton("📊 Status")],
    ],
    resize_keyboard=True,
)


# ===== HANDLERS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "╭─────────────────────────────╮\n"
        "   𝐀𝐍𝐊𝐔𝐒𝐇 𝐇𝐈𝐆𝐇 𝐅𝐎𝐋𝐋𝐎𝐖 𝐓𝐎𝐎𝐋𝐒 🔥\n"
        "╰─────────────────────────────╯\n\n"
        "🤖 *What this bot does:*\n"
        "Automatically scans Instagram accounts and finds ones where "
        "the Gmail username is *still available*. High-follower accounts "
        f"({MIN_FOLLOWERS}+ followers) whose email is unclaimed on Google.\n\n"
        "⚡ *Features:*\n"
        f"› {WORKERS} parallel workers — maximum speed\n"
        "› Auto-refreshes Instagram tokens\n"
        "› Full hit card with email, followers, posts per hit\n\n"
        "👇 *Use the buttons below to control the bot*\n\n"
        "𝐁𝐘 • @z7rnz",
        parse_mode="Markdown",
        reply_markup=MAIN_KB,
    )


async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_tasks[chat_id] = False
    await update.message.reply_text("🛑 Stopping all workers...", reply_markup=MAIN_KB)


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    stats   = user_stats.get(chat_id, {})
    running = user_tasks.get(chat_id, False)
    hits    = len(user_hits.get(chat_id, []))
    await update.message.reply_text(
        f"📊 *Live Stats*\n\n"
        f"🔄 Running : `{'Yes' if running else 'No'}`\n"
        f"✅ Hits    : `{stats.get('hits', 0)}`\n"
        f"👁️ Checked : `{stats.get('checked', 0)}`\n"
        f"❌ Bad     : `{stats.get('bad', 0)}`\n"
        f"📋 Stored  : `{hits}` hit cards",
        parse_mode="Markdown",
        reply_markup=MAIN_KB,
    )


async def hits_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id   = update.effective_chat.id
    hits_list = user_hits.get(chat_id, [])
    if not hits_list:
        await update.message.reply_text(
            "📋 No hits yet.\nPress *🚀 Start Scan* to begin!",
            parse_mode="Markdown",
            reply_markup=MAIN_KB,
        )
        return
    await update.message.reply_text(
        f"📋 *Total Hits: {len(hits_list)}* — sending all cards...",
        parse_mode="Markdown",
        reply_markup=MAIN_KB,
    )
    for h in hits_list:
        kb = [[InlineKeyboardButton("🔍 Profile", url=f"https://www.instagram.com/{h['username']}")]]
        await update.message.reply_text(h["card"], reply_markup=InlineKeyboardMarkup(kb))
        await asyncio.sleep(0.2)


async def keyboard_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text    = update.message.text
    chat_id = update.effective_chat.id

    if text == "🚀 Start Scan":
        if user_tasks.get(chat_id):
            await update.message.reply_text(
                "⚠️ Already running! Press 🛑 Stop Scan first.",
                reply_markup=MAIN_KB,
            )
            return
        asyncio.create_task(run_scanner(chat_id, context.application))

    elif text == "🛑 Stop Scan":
        user_tasks[chat_id] = False
        await update.message.reply_text("🛑 Stopping all workers...", reply_markup=MAIN_KB)

    elif text == "📋 All Hits":
        hits_list = user_hits.get(chat_id, [])
        if not hits_list:
            await update.message.reply_text(
                "📋 No hits yet. Press 🚀 Start Scan first!",
                reply_markup=MAIN_KB,
            )
            return
        await update.message.reply_text(
            f"📋 *Total Hits: {len(hits_list)}* — sending all cards...",
            parse_mode="Markdown",
            reply_markup=MAIN_KB,
        )
        for h in hits_list:
            kb = [[InlineKeyboardButton("🔍 Profile", url=f"https://www.instagram.com/{h['username']}")]]
            await update.message.reply_text(h["card"], reply_markup=InlineKeyboardMarkup(kb))
            await asyncio.sleep(0.2)

    elif text == "📊 Status":
        stats   = user_stats.get(chat_id, {})
        running = user_tasks.get(chat_id, False)
        hits    = len(user_hits.get(chat_id, []))
        await update.message.reply_text(
            f"📊 *Live Stats*\n\n"
            f"🔄 Running : `{'Yes' if running else 'No'}`\n"
            f"✅ Hits    : `{stats.get('hits', 0)}`\n"
            f"👁️ Checked : `{stats.get('checked', 0)}`\n"
            f"❌ Bad     : `{stats.get('bad', 0)}`\n"
            f"📋 Stored  : `{hits}` hit cards",
            parse_mode="Markdown",
            reply_markup=MAIN_KB,
        )


# ===== MAIN =====
def main():
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .connect_timeout(30)
        .read_timeout(30)
        .write_timeout(30)
        .pool_timeout(30)
        .build()
    )
    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("stop",   stop_command))
    app.add_handler(CommandHandler("hits",   hits_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, keyboard_handler))

    print(f"ANKUSH High Follow Bot running with {WORKERS} workers...")
    app.run_polling()


if __name__ == "__main__":
    main()
