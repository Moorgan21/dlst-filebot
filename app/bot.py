import logging

from pyrogram import Client, filters
from pyrogram.types import Message

from . import stats
from .config import API_ID, API_HASH, BOT_TOKEN, BASE_URL, LOG_CHANNEL, ADMIN_ID

logger = logging.getLogger(__name__)

bot = Client(
    "file_to_link_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir="sessions",
)

MEDIA_FILTER = (
    filters.document
    | filters.video
    | filters.audio
    | filters.voice
    | filters.video_note
    | filters.animation
    | filters.photo
)


def _get_media(message: Message):
    for attr in ("document", "video", "audio", "voice", "video_note", "animation", "photo"):
        media = getattr(message, attr, None)
        if media:
            return media
    return None


def _format_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PB"


@bot.on_message(filters.command("start") & filters.private)
async def start_handler(_: Client, message: Message):
    await message.reply_text(
        "🎯 **ربات لینک‌ساز مستقیم تلگرام**\n\n"
        "📤 هر فایلی که برام بفرستی (عکس، ویدیو، سند، صدا، ویس، استیکر و...) رو دریافت می‌کنم و یه **لینک مستقیم** برات می‌سازم.\n\n"
        "🔗 **ویژگی‌های لینک:**\n"
        "• بدون محدودیت حجمی \n"
        "• پشتیبانی از پلی‌بک آنلاین (ویدیو/صدا)\n"
        "• قابلیت **Seek** کردن در پلیر (جا به جا شدن)\n"
        "• دانلود با مدیریت دانلودرها (پشتیبانی از Resume)\n"
        "• بدون ذخیره‌سازی روی سرور (استریم لحظه‌ای)\n\n"
        "📌 **فقط کافیه فایل رو بفرستی، لینک رو برات می‌فرستم.**\n\n"
        "---\n"
        "✨ **Created By D.L**"
    )


@bot.on_message(filters.command("traffic") & filters.private & filters.user(ADMIN_ID))
async def traffic_handler(_: Client, message: Message):
    total = stats.get_total_bytes()
    await message.reply_text(
        f"📊 کل ترافیک فایل‌های استریم‌شده از راه‌اندازی سرویس:\n{_format_bytes(total)}"
    )


@bot.on_message(filters.private & MEDIA_FILTER)
async def file_handler(_: Client, message: Message):
    media = _get_media(message)
    if not media:
        return

    logger.info("file received from chat_id=%s message_id=%s", message.chat.id, message.id)
    status = await message.reply_text("⏳ در حال ساخت لینک ...")

    try:
        if LOG_CHANNEL:
            stored = await message.copy(LOG_CHANNEL)
            chat_id, message_id = LOG_CHANNEL, stored.id
        else:
            chat_id, message_id = message.chat.id, message.id

        link = f"{BASE_URL}/dl/{chat_id}/{message_id}"
        file_name = getattr(media, "file_name", None) or "file"
        file_size = getattr(media, "file_size", 0)

        await status.edit_text(
            f"✅ لینک مستقیم آماده شد:\n\n"
            f"📄 نام: {file_name}\n"
            f"📦 حجم: {file_size / (1024 * 1024):.2f} MB\n\n"
            f"🔗 {link}"
        )
    except Exception:
        logger.exception("failed to generate link")
        await status.edit_text("❌ ساخت لینک با خطا مواجه شد. دوباره امتحان کن.")
