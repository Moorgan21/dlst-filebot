import logging
import time

from . import pyrogram_patch  # noqa: F401  # باید قبل از هر resolve_peer اعمال بشه

from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from . import stats
from .config import (
    API_ID,
    API_HASH,
    BOT_TOKEN,
    BASE_URL,
    FILE_RATE_WINDOW_HOURS,
    FORCE_JOIN_CHANNEL_LINK,
    LINK_TTL_MINUTES,
    LOG_CHANNEL,
    ADMIN_ID,
    MAX_FILES_PER_WINDOW,
    PYROGRAM_WORKERS,
)
from .link_manager import QueueItem, link_manager
from .media import get_media, resolve_file_name_and_mime
from .membership import is_channel_member
from .rate_limit import file_rate_limiter

logger = logging.getLogger(__name__)

MY_LINKS_CALLBACK = "my_links"
GUIDE_CALLBACK = "guide"
BACK_TO_START_CALLBACK = "back_to_start"

MY_LINKS_KEYBOARD = InlineKeyboardMarkup([[
    InlineKeyboardButton("📂 لینک‌های فعال من", callback_data=MY_LINKS_CALLBACK),
    InlineKeyboardButton("❓ راهنما", callback_data=GUIDE_CALLBACK),
]])

BACK_TO_START_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data=BACK_TO_START_CALLBACK)]]
)

JOIN_CHECK_CALLBACK = "check_join"


def _join_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 عضویت در کانال", url=FORCE_JOIN_CHANNEL_LINK)],
        [InlineKeyboardButton("✅ عضو شدم", callback_data=JOIN_CHECK_CALLBACK)],
    ])


async def _require_membership(client: Client, message: Message) -> bool:
    user_id = message.from_user.id if message.from_user else message.chat.id
    if await is_channel_member(client, user_id):
        return True
    await message.reply_text(
        "🔒 برای استفاده از این بات، اول باید عضو کانال زیر بشی:",
        reply_markup=_join_keyboard(),
    )
    return False

bot = Client(
    "file_to_link_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir="sessions",
    workers=PYROGRAM_WORKERS,
)

MEDIA_FILTER = (
    filters.document
    | filters.video
    | filters.audio
    | filters.voice
    | filters.video_note
    | filters.animation
    | filters.photo
    | filters.sticker
)


def _format_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024
    return f"{n:.2f} PB"


START_TEXT = (
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

HELP_TEXT = (
    "❓ **راهنمای ربات**\n\n"
    f"📤 هر {FILE_RATE_WINDOW_HOURS} ساعت فقط می‌تونی {MAX_FILES_PER_WINDOW} فایل برای ساخت لینک بفرستی.\n\n"
    "⛔️ آپلود فایل با محتوای غیرمجاز (مستهجن، غیرقانونی و...) اکیداً ممنوعه؛ در صورت شناسایی، "
    "حساب شما مسدود خواهد شد.\n\n"
    "🔗 لینک‌های ساخته‌شده تا مدت مشخصی معتبرن و بعدش منقضی می‌شن.\n"
    "📂 با دکمه‌ی «لینک‌های فعال من» می‌تونی لینک‌های هنوز معتبرت رو ببینی."
)


@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    if not await _require_membership(client, message):
        return

    await message.reply_text(START_TEXT, reply_markup=MY_LINKS_KEYBOARD)


@bot.on_message(filters.command("traffic") & filters.private & filters.user(ADMIN_ID))
async def traffic_handler(_: Client, message: Message):
    total = stats.get_total_bytes()
    await message.reply_text(
        f"📊 کل ترافیک فایل‌های استریم‌شده از راه‌اندازی سرویس:\n{_format_bytes(total)}"
    )


@bot.on_message(filters.private & MEDIA_FILTER)
async def file_handler(client: Client, message: Message):
    media = get_media(message)
    if not media:
        return

    user_id = message.from_user.id if message.from_user else message.chat.id
    status = None

    try:
        if not await _require_membership(client, message):
            return

        if await link_manager.is_queued(user_id):
            await message.reply_text(
                "⏳ یه درخواست دیگه از تو توی صف منتظره؛ صبر کن نوبتش برسه، بعد فایل جدید بفرست."
            )
            return

        if not await file_rate_limiter.allow(user_id):
            await message.reply_text(
                f"🚫 هر {FILE_RATE_WINDOW_HOURS} ساعت فقط {MAX_FILES_PER_WINDOW} فایل می‌تونی بفرستی. کمی بعد دوباره امتحان کن."
            )
            return

        logger.info("file received from chat_id=%s message_id=%s", message.chat.id, message.id)
        status = await message.reply_text("⏳ در حال ساخت لینک ...", reply_markup=MY_LINKS_KEYBOARD)

        chat_id, message_id = message.chat.id, message.id

        file_name, _ = resolve_file_name_and_mime(media)
        file_size = getattr(media, "file_size", 0)

        if LOG_CHANNEL:
            sender = message.from_user.mention if message.from_user else str(user_id)
            try:
                await bot.send_message(
                    LOG_CHANNEL,
                    "📥 فایل جدید ثبت شد\n\n"
                    f"👤 از: {sender}\n"
                    f"📄 نام: {file_name}\n"
                    f"📦 حجم: {file_size / (1024 * 1024):.2f} MB",
                )
            except Exception:
                logger.exception("failed to send log notification to LOG_CHANNEL")

        token = await link_manager.try_acquire(user_id, chat_id, message_id, file_name, file_size)
        if token is None:
            queued = await link_manager.try_enqueue(QueueItem(
                user_id=user_id,
                notify_chat_id=message.chat.id,
                link_chat_id=chat_id,
                link_message_id=message_id,
                file_name=file_name,
                file_size=file_size,
            ))
            if queued:
                await status.edit_text(
                    "🚦 سرور شلوغه (ظرفیت لینک‌های فعال پره).\n"
                    "درخواستت توی صف قرار گرفت؛ به محض آزاد شدن ظرفیت، لینک برات ارسال می‌شه."
                )
            else:
                # یه درخواست هم‌زمان دیگه از همین کاربر قبل از این یکی صف رو گرفته
                await status.edit_text(
                    "⏳ یه درخواست دیگه از تو توی صف منتظره؛ صبر کن نوبتش برسه، بعد فایل جدید بفرست."
                )
            return

        link = f"{BASE_URL}/dl/{chat_id}/{message_id}?t={token}"

        await status.edit_text(
            f"✅ لینک مستقیم آماده شد:\n\n"
            f"📄 نام: {file_name}\n"
            f"📦 حجم: {file_size / (1024 * 1024):.2f} MB\n\n"
            f"🔗 {link}\n\n"
            f"⏱ این لینک تا {LINK_TTL_MINUTES} دقیقه دیگه معتبره.",
            disable_web_page_preview=True,
        )
    except FloodWait as e:
        logger.warning("FloodWait %ss while handling chat_id=%s", e.value, message.chat.id)
        text = f"⏳ سرور تلگرام موقتاً محدودمون کرده. لطفاً {e.value} ثانیه دیگه دوباره امتحان کن."
        if status:
            await status.edit_text(text)
        else:
            await message.reply_text(text)
    except Exception:
        logger.exception("failed to generate link")
        text = "❌ ساخت لینک با خطا مواجه شد. دوباره امتحان کن."
        if status:
            await status.edit_text(text)
        else:
            await message.reply_text(text)


@bot.on_callback_query(filters.regex(f"^{JOIN_CHECK_CALLBACK}$"))
async def check_join_callback(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    try:
        if await is_channel_member(client, user_id):
            await query.answer("✅ عضویتت تأیید شد!", show_alert=True)
            await query.message.delete()
            await client.send_message(query.message.chat.id, START_TEXT, reply_markup=MY_LINKS_KEYBOARD)
        else:
            await query.answer("❌ هنوز عضو کانال نشدی.", show_alert=True)
    except Exception:
        logger.exception("failed to handle check_join_callback for user_id=%s", user_id)
        try:
            await query.answer("مشکلی پیش اومد. دوباره امتحان کن.", show_alert=True)
        except Exception:
            logger.exception("failed to notify user_id=%s about error in check_join_callback", user_id)


@bot.on_callback_query(filters.regex(f"^{GUIDE_CALLBACK}$"))
async def guide_callback(_: Client, query: CallbackQuery):
    user_id = query.from_user.id
    try:
        await query.message.edit_text(HELP_TEXT, reply_markup=BACK_TO_START_KEYBOARD)
        await query.answer()
    except FloodWait as e:
        logger.warning("FloodWait %ss while handling guide_callback for user_id=%s", e.value, user_id)
        try:
            await query.answer(
                f"سرور تلگرام موقتاً محدودمون کرده، {e.value} ثانیه دیگه امتحان کن.", show_alert=True
            )
        except Exception:
            logger.exception("failed to notify user_id=%s about FloodWait in guide_callback", user_id)
    except Exception:
        logger.exception("failed to handle guide_callback for user_id=%s", user_id)
        try:
            await query.answer("مشکلی پیش اومد. دوباره امتحان کن.", show_alert=True)
        except Exception:
            logger.exception("failed to notify user_id=%s about error in guide_callback", user_id)


@bot.on_callback_query(filters.regex(f"^{BACK_TO_START_CALLBACK}$"))
async def back_to_start_callback(_: Client, query: CallbackQuery):
    user_id = query.from_user.id
    try:
        await query.message.edit_text(START_TEXT, reply_markup=MY_LINKS_KEYBOARD)
        await query.answer()
    except FloodWait as e:
        logger.warning("FloodWait %ss while handling back_to_start_callback for user_id=%s", e.value, user_id)
        try:
            await query.answer(
                f"سرور تلگرام موقتاً محدودمون کرده، {e.value} ثانیه دیگه امتحان کن.", show_alert=True
            )
        except Exception:
            logger.exception("failed to notify user_id=%s about FloodWait in back_to_start_callback", user_id)
    except Exception:
        logger.exception("failed to handle back_to_start_callback for user_id=%s", user_id)
        try:
            await query.answer("مشکلی پیش اومد. دوباره امتحان کن.", show_alert=True)
        except Exception:
            logger.exception("failed to notify user_id=%s about error in back_to_start_callback", user_id)


@bot.on_callback_query(filters.regex(f"^{MY_LINKS_CALLBACK}$"))
async def my_links_callback(_: Client, query: CallbackQuery):
    user_id = query.from_user.id
    try:
        links = await link_manager.list_active_for_user(user_id)

        if not links:
            await query.answer("فعلاً هیچ لینک فعالی نداری.", show_alert=True)
            return

        await query.answer()

        now = time.time()
        lines = ["📂 **لینک‌های فعال تو:**"]
        for i, link in enumerate(links, start=1):
            remaining_min = max(0, int((link.expires_at - now) // 60))
            url = f"{BASE_URL}/dl/{link.chat_id}/{link.message_id}?t={link.token}"
            lines.append(
                f"\n{i}. 📄 {link.file_name} ({link.file_size / (1024 * 1024):.2f} MB)\n"
                f"⏱ {remaining_min} دقیقه تا انقضا\n"
                f"🔗 {url}"
            )

        await query.message.reply_text("\n".join(lines), disable_web_page_preview=True)
    except FloodWait as e:
        logger.warning("FloodWait %ss while handling my_links_callback for user_id=%s", e.value, user_id)
        try:
            await query.answer(
                f"سرور تلگرام موقتاً محدودمون کرده، {e.value} ثانیه دیگه امتحان کن.", show_alert=True
            )
        except Exception:
            logger.exception("failed to notify user_id=%s about FloodWait in my_links_callback", user_id)
    except Exception:
        logger.exception("failed to handle my_links_callback for user_id=%s", user_id)
        try:
            await query.answer("مشکلی پیش اومد. دوباره امتحان کن.", show_alert=True)
        except Exception:
            logger.exception("failed to notify user_id=%s about error in my_links_callback", user_id)


@bot.on_message(filters.private & ~filters.command(["start", "traffic"]))
async def unsupported_handler(client: Client, message: Message):
    if not await _require_membership(client, message):
        return

    await message.reply_text(
        "❌ این نوع پیام/فایل پشتیبانی نمی‌شه.\n\n"
        "چیزهایی که پشتیبانی می‌شن: عکس، ویدیو، گیف، ویس، ویدیو مسیج، آهنگ/موزیک، "
        "استیکر (ثابت یا متحرک) و داکیومنت."
    )
