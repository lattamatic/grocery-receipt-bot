import io
import logging
import os

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from receipt_parser import parse_receipt
from sheets_writer import append_receipt

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi! Send me a photo of a grocery receipt and I'll log every item to your spreadsheet.\n\n"
        "Just snap or forward a clear receipt photo to get started."
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = await update.message.reply_text("Got it! Analysing your receipt...")

    # Download the highest-resolution version of the photo
    photo = update.message.photo[-1]
    tg_file = await context.bot.get_file(photo.file_id)
    buf = io.BytesIO()
    await tg_file.download_to_memory(buf)
    image_bytes = buf.getvalue()

    # Parse with Gemini vision
    try:
        receipt = await parse_receipt(image_bytes)
    except Exception as exc:
        logger.error("Receipt parsing failed: %s", exc)
        await msg.edit_text("Sorry, I couldn't analyse that receipt. Try a clearer photo.")
        return

    if not receipt or not receipt.get("items"):
        await msg.edit_text(
            "I couldn't find any line items on that receipt. "
            "Try a clearer or better-lit photo."
        )
        return

    # Save to Google Sheets
    try:
        rows_saved = append_receipt(receipt)
    except Exception as exc:
        logger.error("Sheets write failed: %s", exc)
        await msg.edit_text("Parsed the receipt but couldn't save to Google Sheets. Check your service account permissions.")
        return

    # Build confirmation message
    store = receipt.get("store_name") or "Unknown Store"
    date = receipt.get("receipt_date") or "unknown date"
    items = receipt.get("items", [])
    total = receipt.get("total")

    lines = [f"✅ Saved {rows_saved} items from *{store}* ({date})\n"]
    for item in items[:8]:
        name = item.get("name", "?")
        qty = item.get("quantity", 1)
        item_total = item.get("total")
        price_str = f"${item_total:.2f}" if item_total is not None else ""
        lines.append(f"• {name}  ×{qty}  {price_str}")
    if len(items) > 8:
        lines.append(f"_...and {len(items) - 8} more items_")
    if total is not None:
        lines.append(f"\n*Receipt total: ${total:.2f}*")

    await msg.edit_text("\n".join(lines), parse_mode="Markdown")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Please send a *photo* of your grocery receipt so I can log it.",
        parse_mode="Markdown",
    )


def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    logger.info("Bot started, polling for updates...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
