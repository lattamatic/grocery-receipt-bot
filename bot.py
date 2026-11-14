import asyncio
import html
import io
import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Must run before the imports below, which read settings from the environment.
load_dotenv()

from receipt_parser import parse_receipt
from sheets_writer import DEFAULT_CURRENCY, append_receipt

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
# httpx logs full request URLs at INFO, and Telegram URLs contain the bot token.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]

# Optional comma-separated chat IDs allowed to use the bot. Empty = anyone.
ALLOWED_CHAT_IDS = {
    int(x) for x in os.environ.get("ALLOWED_CHAT_IDS", "").split(",") if x.strip()
}


def _allowed(update: Update) -> bool:
    return not ALLOWED_CHAT_IDS or update.effective_chat.id in ALLOWED_CHAT_IDS


def _money(value, currency: str) -> str:
    return f"{value:.2f} {currency}" if isinstance(value, (int, float)) else ""


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi! Send me a photo of a grocery receipt and I'll log every item to your spreadsheet.\n\n"
        f"Your chat ID is {update.effective_chat.id}."
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _allowed(update):
        await update.message.reply_text("Sorry, this bot is private.")
        return

    msg = await update.message.reply_text("Got it! Analysing your receipt...")

    # A photo sent "as a file" arrives as a document rather than a photo.
    attachment = update.message.photo[-1] if update.message.photo else update.message.document
    logger.info("Receipt image received from chat %s", update.effective_chat.id)
    tg_file = await context.bot.get_file(attachment.file_id)
    buf = io.BytesIO()
    await tg_file.download_to_memory(buf)

    try:
        mime_type = getattr(attachment, "mime_type", None) or "image/jpeg"
        receipt = await parse_receipt(buf.getvalue(), mime_type)
    except Exception:
        logger.exception("Receipt parsing failed")
        await msg.edit_text(
            "Sorry, I couldn't analyse that receipt right now. Please try again in a minute."
        )
        return

    if not receipt or not receipt.get("items"):
        await msg.edit_text(
            "I couldn't find any line items on that receipt. "
            "Try a clearer or better-lit photo."
        )
        return

    try:
        # Same ID scheme as the rows already in the sheet: <chat id>-<message id>.
        receipt_id = f"{update.effective_chat.id}-{update.message.message_id}"
        rows_saved = await asyncio.to_thread(append_receipt, receipt, receipt_id)
    except Exception:
        logger.exception("Sheets write failed")
        await msg.edit_text(
            "I read the receipt but couldn't save it to Google Sheets. Nothing was added."
        )
        return

    store = html.escape(receipt.get("store_name") or "Unknown Store")
    date = html.escape(receipt.get("receipt_date") or "unknown date")
    items = receipt["items"]
    currency = html.escape(receipt.get("currency") or DEFAULT_CURRENCY)

    lines = [f"✅ Saved {rows_saved} items from <b>{store}</b> ({date})\n"]
    for item in items[:8]:
        name = html.escape(str(item.get("name") or "?"))
        qty = item.get("quantity") or 1
        lines.append(f"• {name}  ×{qty}  {_money(item.get('total'), currency)}")
    if len(items) > 8:
        lines.append(f"<i>...and {len(items) - 8} more items</i>")
    if isinstance(receipt.get("total"), (int, float)):
        lines.append(f"\n<b>Receipt total: {_money(receipt['total'], currency)}</b>")
        items_sum = sum(i["total"] for i in items if isinstance(i.get("total"), (int, float)))
        if abs(items_sum - receipt["total"]) > 0.05:
            lines.append(
                f"⚠️ Items add up to {_money(items_sum, currency)}, which differs from the "
                "receipt total. Please check the rows in the sheet."
            )

    await msg.edit_text("\n".join(lines), parse_mode="HTML")


async def handle_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Non-photo message from chat %s", update.effective_chat.id)
    await update.message.reply_text(
        "Please send a photo of your grocery receipt so I can log it."
    )


def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_photo))
    app.add_handler(MessageHandler(~filters.COMMAND, handle_other))
    logger.info("Bot started, polling for updates...")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
