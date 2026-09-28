import os
import sqlite3
import logging
from datetime import date

from groq import Groq
from telegram import Update, LabeledPrice
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    PreCheckoutQueryHandler,
    ContextTypes,
    filters,
)

# =========================================================
# 🔑 CONFIGURATION
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", "1234567890"))

# Free user daily AI limit
DAILY_FREE_LIMIT = 5

# Telegram Stars price
STARS_PRICE = 50



# =========================================================
# 🤖 GROQ SETTINGS
# =========================================================

MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """
You are Alpha AI, a helpful Telegram AI assistant.

Rules:
- Give accurate, fast, and structured answers.
- If the user asks in Tamil, answer in Tamil.
- If the user asks in Tanglish, answer in Tanglish.
- If the user asks in English, answer in English.
- Keep answers clear and informative.
- Do not invent facts.
"""


# =========================================================
# 📝 LOGGING
# =========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)


# =========================================================
# 🧠 GROQ CLIENT
# =========================================================

client = Groq(
    api_key=GROQ_API_KEY
)


# =========================================================
# 🗄️ SQLITE DATABASE
# =========================================================

DB_NAME = "linkbank.db"


def get_db():
    return sqlite3.connect(
        DB_NAME,
        timeout=10
    )


def init_database():

    conn = get_db()
    cursor = conn.cursor()

    # -----------------------------------------------------
    # LINKS TABLE
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS links (
            keyword TEXT PRIMARY KEY,
            link TEXT NOT NULL
        )
    """)

    # -----------------------------------------------------
    # USERS TABLE
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            is_premium INTEGER DEFAULT 0,
            daily_queries INTEGER DEFAULT 0,
            last_query_date TEXT
        )
    """)

    # -----------------------------------------------------
    # PAYMENTS TABLE
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount INTEGER,
            currency TEXT,
            payload TEXT,
            telegram_payment_id TEXT,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


# =========================================================
# 👤 REGISTER USER
# =========================================================

def register_user(user_id: int):

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR IGNORE INTO users
        (
            user_id,
            is_premium,
            daily_queries,
            last_query_date
        )
        VALUES (?, 0, 0, ?)
        """,
        (
            user_id,
            str(date.today())
        )
    )

    conn.commit()
    conn.close()


# =========================================================
# 🎁 DAILY AI LIMIT
# =========================================================

def check_and_update_limit(user_id: int):

    today = str(date.today())

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            is_premium,
            daily_queries,
            last_query_date
        FROM users
        WHERE user_id = ?
        """,
        (user_id,)
    )

    row = cursor.fetchone()

    # New user
    if not row:

        cursor.execute(
            """
            INSERT INTO users
            (
                user_id,
                is_premium,
                daily_queries,
                last_query_date
            )
            VALUES (?, 0, 1, ?)
            """,
            (
                user_id,
                today
            )
        )

        conn.commit()
        conn.close()

        return True, 1, False

    is_premium, daily_queries, last_query_date = row

    # Premium user
    if is_premium == 1:

        conn.close()

        return True, -1, True

    # New day
    if last_query_date != today:

        cursor.execute(
            """
            UPDATE users
            SET
                daily_queries = 1,
                last_query_date = ?
            WHERE user_id = ?
            """,
            (
                today,
                user_id
            )
        )

        conn.commit()
        conn.close()

        return True, 1, False

    # Limit reached
    if daily_queries >= DAILY_FREE_LIMIT:

        conn.close()

        return False, daily_queries, False

    # Increase query count
    new_count = daily_queries + 1

    cursor.execute(
        """
        UPDATE users
        SET daily_queries = ?
        WHERE user_id = ?
        """,
        (
            new_count,
            user_id
        )
    )

    conn.commit()
    conn.close()

    return True, new_count, False


# =========================================================
# 🚀 /START
# =========================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user = update.effective_user

    register_user(user.id)

    name = user.first_name or "Friend"

    welcome_message = f"""
🤖 <b>ALPHA AI + LINK BANK</b>

━━━━━━━━━━━━━━━━━━
👋 Vanakkam {name}!

⚡ Fast AI Responses
🌐 Tamil / Tanglish / English

🎁 Daily Free Limit:
<b>{DAILY_FREE_LIMIT} AI questions/day</b>

━━━━━━━━━━━━━━━━━━
🔗 <b>LINK BANK</b>

• Save:
<code>/save gemini https://gemini.google.com</code>

• Open:
<code>/gemini</code>

• View All:
<code>/all</code>

• Delete:
<code>/delete gemini</code>

━━━━━━━━━━━━━━━━━━
⭐ <b>PREMIUM</b>

Unlimited AI questions-ku:

👉 <code>/buy</code>

━━━━━━━━━━━━━━━━━━
🧠 <b>ASK ALPHA AI</b>

Any normal message send pannunga.

Example:

<code>What is artificial intelligence?</code>

━━━━━━━━━━━━━━━━━━
🚀 <b>ALPHA AI</b>
"""

    await update.message.reply_text(
        welcome_message,
        parse_mode="HTML",
        disable_web_page_preview=True
    )


# =========================================================
# 🆘 /HELP
# =========================================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    help_text = """
🆘 <b>ALPHA BOT HELP</b>

━━━━━━━━━━━━━━━━━━

🔗 <b>LINK BANK</b>

<code>/save keyword URL</code>
Save a link.

<code>/keyword</code>
Open saved link.

<code>/all</code>
Show all saved links.

<code>/delete keyword</code>
Delete saved link.

━━━━━━━━━━━━━━━━━━

🧠 <b>AI CHAT</b>

Normal text message send pannunga.

Example:

<code>Explain Python</code>

━━━━━━━━━━━━━━━━━━

⭐ <b>PREMIUM</b>

<code>/buy</code>

50 ⭐ Telegram Stars.

━━━━━━━━━━━━━━━━━━
"""

    await update.message.reply_text(
        help_text,
        parse_mode="HTML"
    )


# =========================================================
# 💾 /SAVE
# =========================================================

async def save_link(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    # Admin-only link management
    if update.effective_user.id != ADMIN_ID:

        await update.message.reply_text(
            "⛔ <b>Admin Only</b>\n\n"
            "Link save panna admin permission required.",
            parse_mode="HTML"
        )

        return

    if len(context.args) < 2:

        await update.message.reply_text(
            """
⚠️ <b>Wrong Format</b>

Use:

<code>/save keyword URL</code>

Example:

<code>/save gemini https://gemini.google.com</code>
""",
            parse_mode="HTML"
        )

        return

    keyword = context.args[0].lower().strip()

    link = context.args[1].strip()

    if not (
        link.startswith("http://")
        or
        link.startswith("https://")
    ):

        link = "https://" + link

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT OR REPLACE INTO links
        (
            keyword,
            link
        )
        VALUES (?, ?)
        """,
        (
            keyword,
            link
        )
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"""
✅ <b>LINK SAVED</b>

━━━━━━━━━━━━━━━━━━

🔑 Keyword:
<code>/{keyword}</code>

🔗 Link:
{link}

━━━━━━━━━━━━━━━━━━

Users can now type:

<code>/{keyword}</code>
""",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


# =========================================================
# 📚 /ALL
# =========================================================

async def list_links(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT keyword, link
        FROM links
        ORDER BY keyword ASC
        """
    )

    rows = cursor.fetchall()

    conn.close()

    if not rows:

        await update.message.reply_text(
            "📂 <b>No saved links.</b>",
            parse_mode="HTML"
        )

        return

    message = "📚 <b>ALPHA LINK BANK</b>\n\n"

    keyboard = []

    for keyword, link in rows:

        message += (
            f"🔗 <code>/{keyword}</code>\n"
            f"↳ {link}\n\n"
        )

        keyboard.append(
            [
                InlineKeyboardButton(
                    f"🔗 {keyword.upper()}",
                    url=link
                )
            ]
        )

    await update.message.reply_text(
        message,
        parse_mode="HTML",
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# 🗑️ /DELETE
# =========================================================

async def delete_link(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if update.effective_user.id != ADMIN_ID:

        await update.message.reply_text(
            "⛔ <b>Admin Only</b>",
            parse_mode="HTML"
        )

        return

    if not context.args:

        await update.message.reply_text(
            "⚠️ Use:\n<code>/delete keyword</code>",
            parse_mode="HTML"
        )

        return

    keyword = context.args[0].lower().strip()

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        DELETE FROM links
        WHERE keyword = ?
        """,
        (keyword,)
    )

    deleted = cursor.rowcount

    conn.commit()
    conn.close()

    if deleted > 0:

        await update.message.reply_text(
            f"""
🗑️ <b>LINK DELETED</b>

<code>/{keyword}</code>
""",
            parse_mode="HTML"
        )

    else:

        await update.message.reply_text(
            f"""
❌ <b>Not Found</b>

<code>/{keyword}</code>
database-la illa.
""",
            parse_mode="HTML"
        )


# =========================================================
# 🔗 DYNAMIC LINK COMMAND
# =========================================================

async def handle_saved_link(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    text = update.message.text

    if not text:
        return

    if not text.startswith("/"):
        return

    if " " in text:
        return

    keyword = text[1:].lower().strip()

    if not keyword:
        return

    # Ignore normal bot commands
    normal_commands = {
        "start",
        "help",
        "save",
        "all",
        "delete",
        "buy",
        "premium",
        "broadcast",
        "addpremium"
    }

    if keyword in normal_commands:
        return

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT link
        FROM links
        WHERE keyword = ?
        """,
        (keyword,)
    )

    row = cursor.fetchone()

    conn.close()

    if not row:

        await update.message.reply_text(
            f"""
❌ <b>Link Not Found</b>

<code>/{keyword}</code>

இந்த keyword database-ல் இல்லை.
""",
            parse_mode="HTML"
        )

        return

    link = row[0]

    keyboard = [
        [
            InlineKeyboardButton(
                "🔗 OPEN LINK",
                url=link
            )
        ]
    ]

    await update.message.reply_text(
        f"""
🔗 <b>{keyword.upper()}</b>

━━━━━━━━━━━━━━━━━━

✅ Link Found!

👇 <b>Open using the button</b>
""",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# =========================================================
# ⭐ BUY PREMIUM
# =========================================================

async def buy_premium(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    chat_id = update.effective_chat.id

    title = "⭐ Alpha AI Lifetime Premium"

    description = (
        "Lifetime Premium Access\n\n"
        "• Unlimited AI Questions\n"
        "• No Daily Limit\n"
        "• Priority AI Access\n"
        "• Unlimited Link Bank"
    )

    payload = "alpha_ai_lifetime_sub"

    currency = "XTR"

    prices = [
        LabeledPrice(
            "Lifetime Premium",
            STARS_PRICE
        )
    ]

    await context.bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token="",
        currency=currency,
        prices=prices
    )


# =========================================================
# 💳 PRE-CHECKOUT
# =========================================================

async def precheckout_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.pre_checkout_query

    if query.invoice_payload != "alpha_ai_lifetime_sub":

        await query.answer(
            ok=False,
            error_message="Payment validation failed."
        )

        return

    await query.answer(
        ok=True
    )


# =========================================================
# ✅ SUCCESSFUL PAYMENT
# =========================================================

async def successful_payment_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_id = update.effective_user.id

    payment = update.message.successful_payment

    stars_amount = payment.total_amount

    payment_id = payment.telegram_payment_charge_id

    # Register user
    register_user(user_id)

    conn = get_db()
    cursor = conn.cursor()

    # Activate premium
    cursor.execute(
        """
        UPDATE users
        SET is_premium = 1
        WHERE user_id = ?
        """,
        (user_id,)
    )

    # Save payment record
    cursor.execute(
        """
        INSERT INTO payments
        (
            user_id,
            amount,
            currency,
            payload,
            telegram_payment_id,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            stars_amount,
            payment.currency,
            payment.invoice_payload,
            payment_id,
            str(date.today())
        )
    )

    conn.commit()
    conn.close()

    success_text = f"""
🎉 <b>PAYMENT SUCCESSFUL!</b>

━━━━━━━━━━━━━━━━━━

⭐ Stars Paid:
<b>{stars_amount} ⭐</b>

👑 Status:
<b>PREMIUM ACTIVATED</b>

━━━━━━━━━━━━━━━━━━

🚀 Unlimited AI Questions

⚡ No Daily Limit

🔗 Unlimited Link Bank

━━━━━━━━━━━━━━━━━━

Thank you for supporting
<b>ALPHA AI</b>!
"""

    await update.message.reply_text(
        success_text,
        parse_mode="HTML"
    )


# =========================================================
# 📢 ADMIN BROADCAST
# =========================================================

async def broadcast(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if update.effective_user.id != ADMIN_ID:

        await update.message.reply_text(
            "⛔ Unauthorized."
        )

        return

    if not context.args:

        await update.message.reply_text(
            """
⚠️ <b>Message Missing</b>

Example:

<code>/broadcast Hello everyone!</code>
""",
            parse_mode="HTML"
        )

        return

    broadcast_text = " ".join(context.args)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id FROM users"
    )

    users = cursor.fetchall()

    conn.close()

    await update.message.reply_text(
        f"⏳ Broadcasting to <b>{len(users)}</b> users...",
        parse_mode="HTML"
    )

    delivered = 0
    failed = 0

    for (target_id,) in users:

        try:

            await context.bot.send_message(
                chat_id=target_id,
                text=broadcast_text
            )

            delivered += 1

            # Avoid aggressive Telegram API requests
            await asyncio.sleep(0.05)

        except Exception as error:

            logger.warning(
                "Broadcast failed for %s: %s",
                target_id,
                error
            )

            failed += 1

    await update.message.reply_text(
        f"""
✅ <b>BROADCAST COMPLETED</b>

━━━━━━━━━━━━━━━━━━

📨 Delivered:
<b>{delivered}</b>

❌ Failed/Blocked:
<b>{failed}</b>

━━━━━━━━━━━━━━━━━━
""",
        parse_mode="HTML"
    )


# =========================================================
# 👑 ADMIN ADD PREMIUM
# =========================================================

async def add_premium(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    if update.effective_user.id != ADMIN_ID:

        await update.message.reply_text(
            "⛔ Unauthorized."
        )

        return

    if not context.args:

        await update.message.reply_text(
            """
⚠️ Use:

<code>/addpremium USER_ID</code>
""",
            parse_mode="HTML"
        )

        return

    try:

        target_user_id = int(
            context.args[0]
        )

    except ValueError:

        await update.message.reply_text(
            "❌ Invalid Telegram User ID."
        )

        return

    register_user(target_user_id)

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE users
        SET is_premium = 1
        WHERE user_id = ?
        """,
        (target_user_id,)
    )

    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"""
⭐ <b>PREMIUM ACTIVATED</b>

User:

<code>{target_user_id}</code>
""",
        parse_mode="HTML"
    )


# =========================================================
# 🧠 GROQ AI
# =========================================================

async def ai_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not update.message:
        return

    user_message = update.message.text

    if not user_message:
        return

    user_message = user_message.strip()

    if not user_message:
        return

    if user_message.startswith("/"):
        return

    user_id = update.effective_user.id

    register_user(user_id)

    # -----------------------------------------------------
    # DAILY LIMIT
    # -----------------------------------------------------

    allowed, used_count, is_premium = check_and_update_limit(
        user_id
    )

    if not allowed:

        await update.message.reply_text(
            f"""
⚠️ <b>DAILY FREE LIMIT REACHED</b>

━━━━━━━━━━━━━━━━━━

Today's free AI limit:

<b>{DAILY_FREE_LIMIT}</b>

Neenga already {DAILY_FREE_LIMIT} questions use panniteenga.

━━━━━━━━━━━━━━━━━━

⭐ Unlimited AI access-ku:

<code>/buy</code>

💰 Price:

<b>{STARS_PRICE} ⭐ Stars</b>

━━━━━━━━━━━━━━━━━━
""",
            parse_mode="HTML"
        )

        return

    try:

        await update.message.chat.send_action(
            "typing"
        )

        # Groq is synchronous, so run it outside
        # the Telegram event loop.
        response = await asyncio.to_thread(
            client.chat.completions.create,
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_message
                }
            ],
            temperature=0.7,
            max_tokens=2048
        )

        ai_reply = (
            response.choices[0].message.content
            or
            "No response from AI."
        )

        # -------------------------------------------------
        # FREE USER QUOTA
        # -------------------------------------------------

        if not is_premium:

            remaining = (
                DAILY_FREE_LIMIT
                - used_count
            )

            ai_reply += (
                "\n\n"
                f"[Free Quota: "
                f"{remaining}/"
                f"{DAILY_FREE_LIMIT} "
                f"remaining today]"
            )

        # -------------------------------------------------
        # TELEGRAM MESSAGE LIMIT
        # -------------------------------------------------

        for i in range(
            0,
            len(ai_reply),
            4000
        ):

            chunk = ai_reply[
                i:i + 4000
            ]

            # Plain text is safer because AI may
            # generate Markdown/HTML characters.
            await update.message.reply_text(
                chunk
            )

    except Exception as error:

        logger.exception(
            "Groq/AI error"
        )

        await update.message.reply_text(
            """
❌ <b>AI ERROR</b>

Something went wrong while
connecting to Alpha AI.

Please try again later.
""",
            parse_mode="HTML"
        )


# =========================================================
# ❌ ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    logger.error(
        "Telegram error: %s",
        context.error
    )


# =========================================================
# 🚀 MAIN
# =========================================================

def main():

    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    print(
        "🤖 ALPHA AI + LINK BANK"
    )

    print(
        "⭐ TELEGRAM STARS PREMIUM"
    )

    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    # Initialize database
    init_database()

    # Check configuration
    if (
        BOT_TOKEN == "PASTE_NEW_BOT_TOKEN_HERE"
        or
        not BOT_TOKEN
    ):

        print(
            "❌ BOT_TOKEN is not configured."
        )

        return

    if (
        GROQ_API_KEY == "PASTE_NEW_GROQ_KEY_HERE"
        or
        not GROQ_API_KEY
    ):

        print(
            "❌ GROQ_API_KEY is not configured."
        )

        return

    # -----------------------------------------------------
    # TELEGRAM APPLICATION
    # -----------------------------------------------------

    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    # -----------------------------------------------------
    # BASIC COMMANDS
    # -----------------------------------------------------

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    # -----------------------------------------------------
    # LINK BANK
    # -----------------------------------------------------

    app.add_handler(
        CommandHandler(
            "save",
            save_link
        )
    )

    app.add_handler(
        CommandHandler(
            "all",
            list_links
        )
    )

    app.add_handler(
        CommandHandler(
            "delete",
            delete_link
        )
    )

    # -----------------------------------------------------
    # PREMIUM
    # -----------------------------------------------------

    app.add_handler(
        CommandHandler(
            "buy",
            buy_premium
        )
    )

    app.add_handler(
        CommandHandler(
            "premium",
            buy_premium
        )
    )

    app.add_handler(
        PreCheckoutQueryHandler(
            precheckout_callback
        )
    )

    app.add_handler(
        MessageHandler(
            filters.SUCCESSFUL_PAYMENT,
            successful_payment_callback
        )
    )

    # -----------------------------------------------------
    # ADMIN
    # -----------------------------------------------------

    app.add_handler(
        CommandHandler(
            "broadcast",
            broadcast
        )
    )

    app.add_handler(
        CommandHandler(
            "addpremium",
            add_premium
        )
    )

    # -----------------------------------------------------
    # DYNAMIC LINK COMMANDS
    # -----------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.COMMAND,
            handle_saved_link
        )
    )

    # -----------------------------------------------------
    # AI CHAT
    # -----------------------------------------------------

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            ai_message
        )
    )

    # -----------------------------------------------------
    # ERROR HANDLER
    # -----------------------------------------------------

    app.add_error_handler(
        error_handler
    )

    print(
        "✅ Bot is online!"
    )

    print(
        f"⭐ Premium: {STARS_PRICE} XTR"
    )

    print(
        f"🎁 Free AI: {DAILY_FREE_LIMIT}/day"
    )

    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    # Start bot
    app.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# ▶️ START
# =========================================================

if __name__ == "__main__":
    main()
